"""Builds every component of the monitor and runs the web server.

Typical usage example:

  Application().run()
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

import fastapi
import starlette.middleware.sessions
import uvicorn

from system_monitor.alerts.alert_dispatcher import AlertDispatcher
from system_monitor.alerts.alert_policy import AlertPolicy
from system_monitor.alerts.desktop_notifier import DesktopNotifier
from system_monitor.collectors.data_stores_collector import DataStoresCollector
from system_monitor.collectors.feeds_collector import FeedsCollector
from system_monitor.collectors.log_errors_collector import LogErrorsCollector
from system_monitor.collectors.portfolio_freshness_collector import (
    PortfolioFreshnessCollector,
)
from system_monitor.collectors.quotes_pipeline_collector import (
    QuotesPipelineCollector,
)
from system_monitor.collectors.reference_data_collector import (
    ReferenceDataCollector,
)
from system_monitor.collectors.services_collector import ServicesCollector
from system_monitor.collectors.sessions_collector import SessionsCollector
from system_monitor.collectors.streams_collector import StreamsCollector
from system_monitor.collectors.timers_collector import TimersCollector
from system_monitor.configuration.settings import Settings
from system_monitor.configuration.thresholds import Thresholds
from system_monitor.configuration.unified_broker_interface_configuration import (
    UnifiedBrokerInterfaceConfiguration,
)
from system_monitor.controls.unit_controller import UnitController
from system_monitor.live.api_caller import ApiCaller
from system_monitor.live.api_catalogue import ApiCatalogue
from system_monitor.live.container_inspector import ContainerInspector
from system_monitor.live.database_health import DatabaseHealth
from system_monitor.live.live_view_reader import LiveViewReader
from system_monitor.live.mongodb_health import MongodbHealth
from system_monitor.live.redis_health import RedisHealth
from system_monitor.live.timescaledb_health import TimescaledbHealth
from system_monitor.live.view_catalogue import ViewCatalogue
from system_monitor.routes.auth_routes import AuthRoutes
from system_monitor.routes.control_routes import ControlRoutes
from system_monitor.routes.frontend_routes import FrontendRoutes
from system_monitor.routes.live_routes import LiveRoutes
from system_monitor.routes.log_routes import LogRoutes
from system_monitor.routes.snapshot_routes import SnapshotRoutes
from system_monitor.security.authenticator import Authenticator
from system_monitor.security.session_guard import SessionGuard
from system_monitor.sources.command_runner import CommandRunner
from system_monitor.sources.docker_client import DockerClient
from system_monitor.sources.journal_client import JournalClient
from system_monitor.sources.journal_follower import JournalFollower
from system_monitor.sources.market_calendar import MarketCalendar
from system_monitor.sources.mongo_connection import MongoConnection
from system_monitor.sources.postgres_probe import PostgresProbe
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.rest_api_probe import RestApiProbe
from system_monitor.sources.systemd_client import SystemdClient
from system_monitor.sources.unit_inventory import UnitInventory
from system_monitor.state.collector_scheduler import CollectorScheduler
from system_monitor.state.dashboard_snapshot import DashboardSnapshot
from system_monitor.state.monitor_state import MonitorState
from system_monitor.utilities.clock import SystemClock

_LOGGER = logging.getLogger(__name__)
_SESSION_COOKIE = 'system_monitor_session'


class Application:
    """The whole monitor: sources, collectors, state, controls and web routes.

    Attributes:
        settings: The monitor's settings.
        clock: The source of the current time.
    """

    def __init__(self, settings: Settings | None = None):
        """Creates the application without connecting to anything.

        Args:
            settings (Settings | None): The settings, or None to read them from the environment and .env.
        """
        if settings is None:
            settings = Settings()
        self.settings = settings
        self.clock = SystemClock()
        self.inventory = None
        self.scheduler = None
        self.alert_dispatcher = None
        self.mongo_connection = None

    def run(self) -> None:
        """Builds the application and serves it until stopped.

        Raises:
            ValueError: A setting, the thresholds file or UBI's .env file is invalid.
            FileNotFoundError: The thresholds file or UBI's .env file is missing.
        """
        logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(name)s %(message)s')
        logging.getLogger('httpx').setLevel(logging.WARNING)
        web_application = self.build()
        uvicorn.run(
            web_application,
            host=self.settings.host,
            port=self.settings.port,
            workers=1,
            proxy_headers=False,
            log_config=None,
        )

    def build(self) -> fastapi.FastAPI:
        """Builds every component and the FastAPI application.

        Returns:
            fastapi.FastAPI: The web application, whose startup starts the collectors.

        Raises:
            ValueError: A setting, the thresholds file or UBI's .env file is invalid.
            FileNotFoundError: The thresholds file or UBI's .env file is missing.
        """
        self.settings.require_security_values()
        thresholds = Thresholds.load(self.settings.thresholds_file)
        configuration = UnifiedBrokerInterfaceConfiguration.load(self.settings.unified_broker_interface_directory)
        timeout_seconds = thresholds.data_stores.timeout_seconds

        command_runner = CommandRunner()
        systemd_client = SystemdClient(command_runner)
        journal_client = JournalClient(command_runner)
        self.inventory = UnitInventory(systemd_client, configuration.project_directory / 'services')
        redis_reader = RedisReader.from_configuration(configuration, timeout_seconds)
        self.mongo_connection = MongoConnection(configuration, timeout_seconds)
        market_calendar = MarketCalendar(self.mongo_connection, self.clock)

        collectors = [
            ServicesCollector(systemd_client, self.inventory, thresholds.services, self.clock),
            TimersCollector(systemd_client, self.inventory, self.clock),
            SessionsCollector(redis_reader, self.inventory, self.clock),
            FeedsCollector(redis_reader, self.inventory, market_calendar, thresholds.feeds, self.clock),
            QuotesPipelineCollector(redis_reader, self.inventory, market_calendar, thresholds.quotes_pipeline, self.clock),
            StreamsCollector(redis_reader, self.inventory, thresholds.streams, self.clock),
            PortfolioFreshnessCollector(redis_reader, self.inventory, thresholds.portfolio, self.clock),
            ReferenceDataCollector(redis_reader, self.inventory, thresholds.reference_data, self.clock),
            DataStoresCollector(
                redis_reader,
                self.mongo_connection,
                PostgresProbe(configuration, timeout_seconds),
                RestApiProbe(configuration.rest_api_url, timeout_seconds),
                DockerClient(command_runner),
                thresholds.data_stores,
                self.clock,
            ),
            LogErrorsCollector(journal_client, self.inventory, thresholds.logs, self.clock),
        ]
        state = MonitorState(self.clock)
        alert_policy = AlertPolicy(thresholds.alerts, self.clock)
        self.scheduler = CollectorScheduler(
            collectors,
            state,
            [
                alert_policy,
            ],
        )
        notifier = DesktopNotifier(command_runner, self.settings.desktop_notifications_enabled)
        self.alert_dispatcher = AlertDispatcher(alert_policy, notifier)
        controller = UnitController(systemd_client, self.inventory, self.clock)
        api_catalogue = ApiCatalogue()

        return self.create_web_application(
            snapshot_builder=DashboardSnapshot(state, controller, alert_policy, market_calendar, self.clock),
            controller=controller,
            authenticator=Authenticator(self.settings.password_hash, self.clock),
            inventory=self.inventory,
            journal_follower=JournalFollower(journal_client),
            with_lifespan=True,
            live_routes=LiveRoutes(
                LiveViewReader(redis_reader, ViewCatalogue(), self.inventory),
                DatabaseHealth(
                    RedisHealth(redis_reader),
                    MongodbHealth(self.mongo_connection),
                    TimescaledbHealth(configuration, timeout_seconds),
                    ContainerInspector(command_runner),
                    self.clock,
                ),
                api_catalogue,
                ApiCaller(
                    api_catalogue,
                    redis_reader,
                    configuration.rest_api_url,
                    thresholds.live_view.api_timeout_seconds,
                ),
                SessionGuard(),
            ),
        )

    def create_web_application(
        self,
        snapshot_builder: DashboardSnapshot,
        controller: UnitController,
        authenticator: Authenticator,
        inventory: UnitInventory,
        journal_follower: JournalFollower,
        with_lifespan: bool,
        live_routes: LiveRoutes | None = None,
    ) -> fastapi.FastAPI:
        """Assembles the FastAPI application from ready components.

        Tests call this with fake components and without the lifespan.

        Args:
            snapshot_builder (DashboardSnapshot): Builds the dashboard document.
            controller (UnitController): Performs unit actions.
            authenticator (Authenticator): Checks the password.
            inventory (UnitInventory): The units whose logs may be read.
            journal_follower (JournalFollower): Follows a unit's journal.
            with_lifespan (bool): Whether startup should refresh the inventory and start the collectors.
            live_routes (LiveRoutes | None): The live view's routes, or None to leave the page's routes unmounted. They are left out by tests that have no live stores to read.

        Returns:
            fastapi.FastAPI: The web application.
        """
        lifespan = None
        if with_lifespan:
            lifespan = self._lifespan
        web_application = fastapi.FastAPI(
            title='System monitor',
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
            lifespan=lifespan,
        )
        web_application.add_middleware(
            starlette.middleware.sessions.SessionMiddleware,
            secret_key=self.settings.session_secret,
            session_cookie=_SESSION_COOKIE,
            max_age=self.settings.session_max_age_seconds,
            same_site='strict',
            https_only=False,
        )
        guard = SessionGuard()
        web_application.include_router(AuthRoutes(authenticator, guard, self.clock).router)
        web_application.include_router(SnapshotRoutes(snapshot_builder, guard).router)
        web_application.include_router(LogRoutes(inventory, journal_follower, guard).router)
        web_application.include_router(ControlRoutes(controller, guard).router)
        if live_routes is not None:
            web_application.include_router(live_routes.router)
        web_application.include_router(FrontendRoutes(self.settings.frontend_directory).router)
        return web_application

    @contextlib.asynccontextmanager
    async def _lifespan(self, web_application: fastapi.FastAPI) -> AsyncIterator[None]:
        """Starts the collectors when the server starts and stops them when it stops.

        Args:
            web_application (fastapi.FastAPI): The application being started.

        Yields:
            None: Control returns to the server while the application runs.
        """
        del web_application
        await asyncio.to_thread(self.inventory.refresh)
        _LOGGER.info('Found %d units under %d targets.', len(self.inventory.units()), len(self.inventory.subjects()))
        scheduler_task = asyncio.create_task(self.scheduler.run())
        dispatcher_task = asyncio.create_task(self.alert_dispatcher.run())
        try:
            yield
        finally:
            for task in (
                scheduler_task,
                dispatcher_task,
            ):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self.mongo_connection.close()
