from __future__ import absolute_import, print_function

import signal
import sys
from multiprocessing import cpu_count

import click

from sentry.runner.decorators import configuration, log_options
from sentry.bgtasks.api import managed_bgtasks


class AddressParamType(click.ParamType):
    name = "address"

    def __call__(self, value, param=None, ctx=None):
        if value is None:
            return (None, None)
        return self.convert(value, param, ctx)

    def convert(self, value, param, ctx):
        if ":" in value:
            host, port = value.split(":", 1)
            port = int(port)
        else:
            host = value
            port = None
        return host, port


Address = AddressParamType()


class QueueSetType(click.ParamType):
    name = "text"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        # Providing a compatibility with splitting
        # the `events` queue until multiple queues
        # without the need to explicitly add them.
        queues = set()
        for queue in value.split(","):
            if queue == "events":
                queues.add("events.preprocess_event")
                queues.add("events.process_event")
                queues.add("events.save_event")

                from sentry.runner.initializer import show_big_error

                show_big_error(
                    [
                        "DEPRECATED",
                        "`events` queue no longer exists.",
                        "Switch to using:",
                        "- events.preprocess_event",
                        "- events.process_event",
                        "- events.save_event",
                    ]
                )
            else:
                queues.add(queue)
        return frozenset(queues)


QueueSet = QueueSetType()


@click.group()
def run():
    "Run a service."


@run.command()
@click.option("--bind", "-b", default=None, help="Bind address.", type=Address)
@click.option(
    "--workers", "-w", default=0, help="The number of worker processes for handling requests."
)
@click.option("--upgrade", default=False, is_flag=True, help="Upgrade before starting.")
@click.option(
    "--with-lock", default=False, is_flag=True, help="Use a lock if performing an upgrade."
)
@click.option(
    "--noinput", default=False, is_flag=True, help="Do not prompt the user for input of any kind."
)
@click.option(
    "--uwsgi/--no-uwsgi",
    default=True,
    is_flag=True,
    help="Use uWSGI (default) or non-uWSGI (useful for debuggers such as PyCharm's)",
)
@log_options()
@configuration
def web(bind, workers, upgrade, with_lock, noinput, uwsgi):
    "Run web service."
    if upgrade:
        click.echo("Performing upgrade before service startup...")
        from sentry.runner import call_command

        try:
            call_command(
                "sentry.runner.commands.upgrade.upgrade",
                verbosity=0,
                noinput=noinput,
                lock=with_lock,
            )
        except click.ClickException:
            if with_lock:
                click.echo("!! Upgrade currently running from another process, skipping.", err=True)
            else:
                raise

    with managed_bgtasks(role="web"):
        if not uwsgi:
            click.echo(
                "Running simple HTTP server. Note that chunked file "
                "uploads will likely not work.",
                err=True,
            )

            from django.conf import settings

            host = bind[0] or settings.SENTRY_WEB_HOST
            port = bind[1] or settings.SENTRY_WEB_PORT
            click.echo("Address: http://%s:%s/" % (host, port))

            from wsgiref.simple_server import make_server
            from sentry.wsgi import application

            httpd = make_server(host, port, application)
            httpd.serve_forever()
        else:
            from sentry.services.http import SentryHTTPServer

            SentryHTTPServer(host=bind[0], port=bind[1], workers=workers).run()


@run.command()
@click.option("--bind", "-b", default=None, help="Bind address.", type=Address)
@click.option("--upgrade", default=False, is_flag=True, help="Upgrade before starting.")
@click.option(
    "--noinput", default=False, is_flag=True, help="Do not prompt the user for input of any kind."
)
@configuration
def smtp(bind, upgrade, noinput):
    "Run inbound email service."
    if upgrade:
        click.echo("Performing upgrade before service startup...")
        from sentry.runner import call_command

        call_command("sentry.runner.commands.upgrade.upgrade", verbosity=0, noinput=noinput)

    from sentry.services.smtp import SentrySMTPServer

    with managed_bgtasks(role="smtp"):
        SentrySMTPServer(host=bind[0], port=bind[1]).run()


@run.command()
@click.option(
    "--hostname",
    "-n",
    help=(
        "Set custom hostname, e.g. 'w1.%h'. Expands: %h" "(hostname), %n (name) and %d, (domain)."
    ),
)
@click.option(
    "--queues",
    "-Q",
    type=QueueSet,
    help=(
        "List of queues to enable for this worker, separated by "
        "comma. By default all configured queues are enabled. "
        "Example: -Q video,image"
    ),
)
@click.option("--exclude-queues", "-X", type=QueueSet)
@click.option(
    "--concurrency",
    "-c",
    default=cpu_count(),
    help=(
        "Number of child processes processing the queue. The "
        "default is the number of CPUs available on your "
        "system."
    ),
)
@click.option(
    "--logfile", "-f", help=("Path to log file. If no logfile is specified, stderr is used.")
)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.option("--no-color", is_flag=True, default=False)
@click.option("--autoreload", is_flag=True, default=False, help="Enable autoreloading.")
@click.option("--without-gossip", is_flag=True, default=False)
@click.option("--without-mingle", is_flag=True, default=False)
@click.option("--without-heartbeat", is_flag=True, default=False)
@click.option("--max-tasks-per-child", default=10000)
@log_options()
@configuration
def worker(**options):
    "Run background worker instance."
    from django.conf import settings

    if settings.CELERY_ALWAYS_EAGER:
        raise click.ClickException(
            "Disable CELERY_ALWAYS_EAGER in your settings file to spawn workers."
        )

    from sentry.celery import app

    with managed_bgtasks(role="worker"):
        worker = app.Worker(
            # without_gossip=True,
            # without_mingle=True,
            # without_heartbeat=True,
            pool_cls="processes",
            **options
        )
        worker.start()
        try:
            sys.exit(worker.exitcode)
        except AttributeError:
            # `worker.exitcode` was added in a newer version of Celery:
            # https://github.com/celery/celery/commit/dc28e8a5
            # so this is an attempt to be forwards compatible
            pass


@run.command()
@click.option(
    "--pidfile",
    help=(
        "Optional file used to store the process pid. The "
        "program will not start if this file already exists and "
        "the pid is still alive."
    ),
)
@click.option(
    "--logfile", "-f", help=("Path to log file. If no logfile is specified, stderr is used.")
)
@click.option("--quiet", "-q", is_flag=True, default=False)
@click.option("--no-color", is_flag=True, default=False)
@click.option("--autoreload", is_flag=True, default=False, help="Enable autoreloading.")
@click.option("--without-gossip", is_flag=True, default=False)
@click.option("--without-mingle", is_flag=True, default=False)
@click.option("--without-heartbeat", is_flag=True, default=False)
@log_options()
@configuration
def cron(**options):
    "Run periodic task dispatcher."
    from django.conf import settings

    if settings.CELERY_ALWAYS_EAGER:
        raise click.ClickException(
            "Disable CELERY_ALWAYS_EAGER in your settings file to spawn workers."
        )

    from sentry.celery import app

    with managed_bgtasks(role="cron"):
        app.Beat(
            # without_gossip=True,
            # without_mingle=True,
            # without_heartbeat=True,
            **options
        ).run()


@run.command("post-process-forwarder")
@click.option(
    "--consumer-group",
    default="snuba-post-processor",
    help="Consumer group used to track event offsets that have been enqueued for post-processing.",
)
@click.option(
    "--commit-log-topic",
    default="snuba-commit-log",
    help="Topic that the Snuba writer is publishing its committed offsets to.",
)
@click.option(
    "--synchronize-commit-group",
    default="snuba-consumers",
    help="Consumer group that the Snuba writer is committing its offset as.",
)
@click.option(
    "--commit-batch-size",
    default=1000,
    type=int,
    help="How many messages to process (may or may not result in an enqueued task) before committing offsets.",
)
@click.option(
    "--initial-offset-reset",
    default="latest",
    type=click.Choice(["earliest", "latest"]),
    help="Position in the commit log topic to begin reading from when no prior offset has been recorded.",
)
@log_options()
@configuration
def post_process_forwarder(**options):
    from sentry import eventstream
    from sentry.eventstream.base import ForwarderNotRequired

    try:
        eventstream.run_post_process_forwarder(
            consumer_group=options["consumer_group"],
            commit_log_topic=options["commit_log_topic"],
            synchronize_commit_group=options["synchronize_commit_group"],
            commit_batch_size=options["commit_batch_size"],
            initial_offset_reset=options["initial_offset_reset"],
        )
    except ForwarderNotRequired:
        sys.stdout.write(
            "The configured event stream backend does not need a forwarder "
            "process to enqueue post-process tasks. Exiting...\n"
        )
        return


@run.command("query-subscription-consumer")
@click.option(
    "--group",
    default="query-subscription-consumer",
    help="Consumer group to track query subscription offsets. ",
)
@click.option("--topic", default=None, help="Topic to get subscription updates from.")
@click.option(
    "--commit-batch-size",
    default=100,
    type=int,
    help="How many messages to process before committing offsets.",
)
@click.option(
    "--initial-offset-reset",
    default="latest",
    type=click.Choice(["earliest", "latest"]),
    help="Position in the commit log topic to begin reading from when no prior offset has been recorded.",
)
@log_options()
@configuration
def query_subscription_consumer(**options):
    from sentry.snuba.query_subscription_consumer import QuerySubscriptionConsumer

    subscriber = QuerySubscriptionConsumer(
        group_id=options["group"],
        topic=options["topic"],
        commit_batch_size=options["commit_batch_size"],
        initial_offset_reset=options["initial_offset_reset"],
    )

    def handler(signum, frame):
        subscriber.shutdown()

    signal.signal(signal.SIGINT, handler)

    subscriber.run()


@run.command("ingest-consumer")
@log_options()
@click.option(
    "--consumer-type",
    default=None,
    help="Specify which type of consumer to create, i.e. from which topic to consume messages.",
    type=click.Choice(["events", "transactions", "attachments"]),
)
@click.option(
    "--group", default="ingest-consumer", help="Kafka consumer group for the ingest consumer. "
)
@click.option(
    "--commit-batch-size",
    default=100,
    type=int,
    help="How many messages to process before committing offsets.",
)
@click.option(
    "--max-fetch-time-ms",
    default=100,
    type=int,
    help="Timeout (in milliseconds) for a consume operation. Max time the kafka consumer will wait "
    "before returning the available messages in the topic.",
)
@click.option(
    "--initial-offset-reset",
    default="latest",
    type=click.Choice(["earliest", "latest", "error"]),
    help="Position in the commit log topic to begin reading from when no prior offset has been recorded.",
)
@configuration
def ingest_consumer(**options):
    """
    Runs an "ingest consumer" task.

    The "ingest consumer" tasks read events from a kafka topic (coming from Relay) and schedules
    process event celery tasks for them
    """
    from sentry.ingest.ingest_consumer import ConsumerType, run_ingest_consumer

    consumer_type = options["consumer_type"]
    if consumer_type == "events":
        consumer_type = ConsumerType.Events
    elif consumer_type == "transactions":
        consumer_type = ConsumerType.Transactions
    elif consumer_type == "attachments":
        consumer_type = ConsumerType.Attachments

    max_fetch_time_seconds = options["max_fetch_time_ms"] / 1000.0

    run_ingest_consumer(
        commit_batch_size=options["commit_batch_size"],
        consumer_group=options["group"],
        consumer_type=consumer_type,
        max_fetch_time_seconds=max_fetch_time_seconds,
        initial_offset_reset=options["initial_offset_reset"],
    )


@run.command("outcomes-consumer")
@log_options()
@click.option(
    "--group", default="outcomes-consumer", help="Kafka consumer group for the outcomes consumer. "
)
@click.option(
    "--commit-batch-size",
    default=100,
    type=int,
    help="How many messages to process before committing offsets.",
)
@click.option(
    "--max-fetch-time-ms",
    default=100,
    type=int,
    help="Timeout (in milliseconds) for a consume operation. Max time the kafka consumer will wait "
    "before returning the available messages in the topic.",
)
@click.option(
    "--initial-offset-reset",
    default="latest",
    type=click.Choice(["earliest", "latest", "error"]),
    help="Position in the commit log topic to begin reading from when no prior offset has been recorded.",
)
@configuration
def outcome_consumer(**options):
    """
    Runs an "outcomes consumer" task.

    The "outcomes consumer" tasks read outcomes from a kafka topic and sends
    signals for some of them.
    """
    from sentry.ingest.outcome_consumer import run_outcomes_consumer

    max_fetch_time_seconds = options["max_fetch_time_ms"] / 1000.0

    run_outcomes_consumer(
        commit_batch_size=options["commit_batch_size"],
        consumer_group=options["group"],
        max_fetch_time_seconds=max_fetch_time_seconds,
        initial_offset_reset=options["initial_offset_reset"],
    )
