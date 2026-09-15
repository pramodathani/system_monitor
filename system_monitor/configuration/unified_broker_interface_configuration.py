"""Connection details for the stores of unified_broker_interface.

The details are read from that project's own `.env` file, so the monitor never keeps a second copy of its passwords.

Typical usage example:

  configuration = UnifiedBrokerInterfaceConfiguration.load(directory)
  print(configuration.redis_host)
"""

from pathlib import Path

from dotenv import dotenv_values

_PREFIX = 'UNIFIED_BROKER_INTERFACE_'


class UnifiedBrokerInterfaceConfiguration:
    """The addresses and credentials of Redis, MongoDB, TimescaleDB and the REST API.

    Attributes:
        project_directory: The unified_broker_interface project directory.
        redis_host: The Redis host.
        redis_port: The Redis port.
        redis_database: The Redis database number.
        redis_username: The Redis user name, or None.
        redis_password: The Redis password, or None.
        mongodb_host: The MongoDB host.
        mongodb_port: The MongoDB port.
        mongodb_database: The MongoDB database name.
        mongodb_username: The MongoDB user name, or None.
        mongodb_password: The MongoDB password, or None.
        postgres_host: The TimescaleDB host.
        postgres_port: The TimescaleDB port.
        postgres_database: The TimescaleDB database name.
        postgres_username: The TimescaleDB user name, or None.
        postgres_password: The TimescaleDB password, or None.
        rest_api_url: The address of the REST API's unauthenticated greeting route.
    """

    def __init__(
        self,
        project_directory: Path,
        values: dict[str, str | None],
    ):
        """Builds the configuration from the values of a `.env` file.

        Args:
            project_directory (Path): The unified_broker_interface project directory.
            values (dict[str, str | None]): The variables read from the project's `.env` file.

        Raises:
            ValueError: A required variable is missing or a port is not a number.
        """
        self.project_directory = project_directory
        self._values = values
        self.redis_host = self._required('REDIS_HOST')
        self.redis_port = self._required_number('REDIS_PORT')
        self.redis_database = self._required_number('REDIS_DB')
        self.redis_username = self._optional('REDIS_USERNAME')
        self.redis_password = self._optional('REDIS_PASSWORD')
        self.mongodb_host = self._required('MONGODB_HOST')
        self.mongodb_port = self._required_number('MONGODB_PORT')
        self.mongodb_database = self._required('MONGODB_DB')
        self.mongodb_username = self._optional('MONGODB_USERNAME')
        self.mongodb_password = self._optional('MONGODB_PASSWORD')
        self.postgres_host = self._required('POSTGRES_HOST')
        self.postgres_port = self._required_number('POSTGRES_PORT')
        self.postgres_database = self._required('POSTGRES_DB')
        self.postgres_username = self._optional('POSTGRES_USERNAME')
        self.postgres_password = self._optional('POSTGRES_PASSWORD')
        api_host = self._optional('API_HOST') or '127.0.0.1'
        api_port = self._optional('API_PORT') or '8080'
        self.rest_api_url = f'http://{api_host}:{api_port}/api/'

    @classmethod
    def load(cls, project_directory: Path) -> UnifiedBrokerInterfaceConfiguration:
        """Reads the configuration from the project's `.env` file.

        Args:
            project_directory (Path): The unified_broker_interface project directory.

        Returns:
            UnifiedBrokerInterfaceConfiguration: The configuration read from the file.

        Raises:
            FileNotFoundError: The project has no `.env` file.
            ValueError: A required variable is missing or a port is not a number.
        """
        environment_file = project_directory / '.env'
        if not environment_file.is_file():
            raise FileNotFoundError(f'No .env file in the unified_broker_interface directory: {environment_file}')
        return cls(project_directory, dotenv_values(environment_file))

    def _optional(self, name: str) -> str | None:
        """Reads a variable that may be absent or empty.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            str | None: The value, or None when it is absent or empty.
        """
        value = self._values.get(_PREFIX + name)
        if not value:
            return None
        return value

    def _required(self, name: str) -> str:
        """Reads a variable that must be present.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            str: The value.

        Raises:
            ValueError: The variable is absent or empty.
        """
        value = self._optional(name)
        if value is None:
            raise ValueError(f'Missing variable in the unified_broker_interface .env file: {_PREFIX + name}')
        return value

    def _required_number(self, name: str) -> int:
        """Reads a variable that must hold a whole number.

        Args:
            name (str): The variable name without the UNIFIED_BROKER_INTERFACE_ prefix.

        Returns:
            int: The value as a number.

        Raises:
            ValueError: The variable is absent, empty or not a whole number.
        """
        text = self._required(name)
        try:
            return int(text)
        except ValueError as error:
            raise ValueError(f'Not a whole number in the unified_broker_interface .env file: {_PREFIX + name}={text!r}') from error
