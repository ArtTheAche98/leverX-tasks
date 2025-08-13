from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any
import json
import mysql.connector
from pathlib import Path
import logging.config


LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'student_analytics.log',
            'mode': 'a'
        }
    },
    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': ['console', 'file']
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

@dataclass
class Student:
    id: int
    name: str
    birthday: str
    room: int
    sex: str


@dataclass
class Room:
    id: int
    name: str


class DatabaseConnectionInterface(ABC):
    @abstractmethod
    def connect(self) -> mysql.connector.MySQLConnection:
        pass


class DataLoaderInterface(ABC):
    @abstractmethod
    def load_students(self, file_path: Path) -> List[Student]:
        pass

    @abstractmethod
    def load_rooms(self, file_path: Path) -> List[Room]:
        pass


class DatabaseSchemaManagerInterface(ABC):
    @abstractmethod
    def create_schema(self, connection: mysql.connector.MySQLConnection) -> None:
        pass


class DataInserterInterface(ABC):
    @abstractmethod
    def insert_students(self, connection: mysql.connector.MySQLConnection, students: List[Student]) -> None:
        pass

    @abstractmethod
    def insert_rooms(self, connection: mysql.connector.MySQLConnection, rooms: List[Room]) -> None:
        pass


class StudentRoomAnalyticsInterface(ABC):
    @abstractmethod
    def get_rooms_with_student_count(self, connection: mysql.connector.MySQLConnection) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_top_rooms_by_avg_age(self, connection: mysql.connector.MySQLConnection, limit: int = 5) -> List[
        Dict[str, Any]]:
        pass

    @abstractmethod
    def get_top_rooms_by_age_difference(self, connection: mysql.connector.MySQLConnection, limit: int = 5) -> List[
        Dict[str, Any]]:
        pass

    @abstractmethod
    def get_mixed_gender_rooms(self, connection: mysql.connector.MySQLConnection) -> List[Dict[str, Any]]:
        pass


class MySQLDatabaseConnection(DatabaseConnectionInterface):
    def __init__(self, host: str, user: str, password: str, database: str):
        self.host = host
        self.user = user
        self.password = password
        self.database = database

    def connect(self) -> mysql.connector.MySQLConnection:
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            logger.info("Database connection established successfully")
            return connection
        except mysql.connector.Error as error:
            logger.exception(f"Failed to connect to database: {error}")
            raise


class JSONDataLoader(DataLoaderInterface):
    def load_students(self, file_path: Path) -> List[Student]:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                students_data = json.load(file)
                students = [
                    Student(
                        id=student_data['id'],
                        name=student_data['name'],
                        birthday=student_data['birthday'],
                        room=student_data['room'],
                        sex=student_data['sex']
                    )
                    for student_data in students_data
                ]
                logger.info(f"Loaded {len(students)} students from {file_path}")
                return students
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as error:
            logger.exception(f"Failed to load students from {file_path}")
            raise

    def load_rooms(self, file_path: Path) -> List[Room]:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                rooms_data = json.load(file)
                rooms = [
                    Room(id=room_data['id'], name=room_data['name'])
                    for room_data in rooms_data
                ]
                logger.info(f"Loaded {len(rooms)} rooms from {file_path}")
                return rooms
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as error:
            logger.exception(f"Failed to load rooms from {file_path}")
            raise


class MySQLSchemaManager(DatabaseSchemaManagerInterface):
    def create_schema(self, connection: mysql.connector.MySQLConnection) -> None:
        cursor = connection.cursor()
        try:
            # Create rooms table
            create_rooms_table = """
                CREATE TABLE IF NOT EXISTS rooms (
                    id INT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    INDEX idx_room_id (id)
                ) ENGINE=InnoDB
            """

            # Create students table with foreign key
            create_students_table = """
                CREATE TABLE IF NOT EXISTS students (
                    id INT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    birthday DATE NOT NULL,
                    room INT NOT NULL,
                    sex ENUM('M', 'F') NOT NULL,
                    FOREIGN KEY (room) REFERENCES rooms(id),
                    INDEX idx_student_room (room),
                    INDEX idx_student_sex (sex),
                    INDEX idx_student_birthday (birthday)
                ) ENGINE=InnoDB
            """

            cursor.execute(create_rooms_table)
            cursor.execute(create_students_table)
            connection.commit()
            logger.info("Database schema created successfully")

            self._log_index_recommendations()

        except mysql.connector.Error as error:
            logger.exception("Failed to create database schema")
            connection.rollback()
            raise
        finally:
            cursor.close()

    def _log_index_recommendations(self) -> None:
        """Log recommended indexes for query optimization"""
        recommendations = [
            "Index Optimization Recommendations:",
            "1. idx_student_room (room) - Already created for JOIN operations",
            "2. idx_student_birthday (birthday) - Already created for age calculations",
            "3. idx_student_sex (sex) - Already created for gender filtering",
            "4. Consider composite index (room, sex) for mixed gender queries",
            "5. Consider composite index (room, birthday) for age-related room queries"
        ]
        for rec in recommendations:
            logger.info(rec)

    def create_optimized_indexes(self, connection: mysql.connector.MySQLConnection) -> None:
        """Create additional composite indexes for better query performance"""
        cursor = connection.cursor()
        try:
            cursor.execute("CREATE INDEX idx_room_sex ON students(room, sex)")

            cursor.execute("CREATE INDEX idx_room_birthday ON students(room, birthday)")

            connection.commit()
            logger.info("Optimized indexes created successfully")

        except mysql.connector.Error as error:
            logger.warning(f"Could not create optimized indexes: {error}")
        finally:
            cursor.close()

class MySQLDataInserter(DataInserterInterface):
    def insert_rooms(self, connection: mysql.connector.MySQLConnection, rooms: List[Room]) -> None:
        cursor = connection.cursor()
        try:
            # Clear existing data
            cursor.execute("DELETE FROM students")
            cursor.execute("DELETE FROM rooms")

            insert_room_query = "INSERT INTO rooms (id, name) VALUES (%s, %s)"
            room_values = [(room.id, room.name) for room in rooms]

            cursor.executemany(insert_room_query, room_values)
            connection.commit()
            logger.info(f"Inserted {len(rooms)} rooms successfully")

        except mysql.connector.Error as error:
            logger.exception("Failed to insert rooms")
            connection.rollback()
            raise
        finally:
            cursor.close()

    def insert_students(self, connection: mysql.connector.MySQLConnection, students: List[Student]) -> None:
        cursor = connection.cursor()
        try:
            insert_student_query = """
                                   INSERT INTO students (id, name, birthday, room, sex)
                                   VALUES (%s, %s, %s, %s, %s) \
                                   """
            student_values = [
                (student.id, student.name, student.birthday, student.room, student.sex)
                for student in students
            ]

            cursor.executemany(insert_student_query, student_values)
            connection.commit()
            logger.info(f"Inserted {len(students)} students successfully")

        except mysql.connector.Error as error:
            logger.exception("Failed to insert students")
            connection.rollback()
            raise
        finally:
            cursor.close()


class StudentRoomAnalytics(StudentRoomAnalyticsInterface):
    def get_rooms_with_student_count(self, connection: mysql.connector.MySQLConnection) -> List[Dict[str, Any]]:
        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                    SELECT r.id, r.name, COUNT(s.id) as student_count
                    FROM rooms r
                             LEFT JOIN students s ON r.id = s.room
                    GROUP BY r.id, r.name
                    ORDER BY student_count DESC, r.id \
                    """
            cursor.execute(query)
            results = cursor.fetchall()
            logger.info(f"Retrieved room student counts for {len(results)} rooms")
            return results
        except mysql.connector.Error as error:
            logger.exception("Failed to get rooms with student count")
            raise
        finally:
            cursor.close()

    def get_top_rooms_by_avg_age(self, connection: mysql.connector.MySQLConnection, limit: int = 5) -> List[
        Dict[str, Any]]:
        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                    SELECT r.id, \
                           r.name,
                           AVG(DATEDIFF(CURDATE(), s.birthday) / 365.25) as avg_age
                    FROM rooms r
                             INNER JOIN students s ON r.id = s.room
                    GROUP BY r.id, r.name
                    HAVING COUNT(s.id) > 0
                    ORDER BY avg_age ASC
                        LIMIT %s \
                    """
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            logger.info(f"Retrieved top {limit} rooms by average age")
            return results
        except mysql.connector.Error as error:
            logger.exception("Failed to get top rooms by average age")
            raise
        finally:
            cursor.close()

    def get_top_rooms_by_age_difference(self, connection: mysql.connector.MySQLConnection, limit: int = 5) -> List[
        Dict[str, Any]]:
        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                    SELECT r.id, \
                           r.name,
                           (MAX(DATEDIFF(CURDATE(), s.birthday) / 365.25) -
                            MIN(DATEDIFF(CURDATE(), s.birthday) / 365.25)) as age_difference
                    FROM rooms r
                             INNER JOIN students s ON r.id = s.room
                    GROUP BY r.id, r.name
                    HAVING COUNT(s.id) > 1
                    ORDER BY age_difference DESC
                        LIMIT %s \
                    """
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            logger.info(f"Retrieved top {limit} rooms by age difference")
            return results
        except mysql.connector.Error as error:
            logger.exception("Failed to get top rooms by age difference")
            raise
        finally:
            cursor.close()

    def get_mixed_gender_rooms(self, connection: mysql.connector.MySQLConnection) -> List[Dict[str, Any]]:
        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                    SELECT r.id, r.name
                    FROM rooms r
                    WHERE EXISTS (SELECT 1 \
                                  FROM students s1 \
                                  WHERE s1.room = r.id AND s1.sex = 'M') \
                      AND EXISTS (SELECT 1 \
                                  FROM students s2 \
                                  WHERE s2.room = r.id AND s2.sex = 'F')
                    ORDER BY r.id \
                    """
            cursor.execute(query)
            results = cursor.fetchall()
            logger.info(f"Retrieved {len(results)} mixed gender rooms")
            return results
        except mysql.connector.Error as error:
            logger.exception("Failed to get mixed gender rooms")
            raise
        finally:
            cursor.close()


class StudentRoomAnalyticsApplication:
    def __init__(
            self,
            database_connection: DatabaseConnectionInterface,
            data_loader: DataLoaderInterface,
            schema_manager: DatabaseSchemaManagerInterface,
            data_inserter: DataInserterInterface,
            analytics: StudentRoomAnalyticsInterface
    ):
        self.database_connection = database_connection
        self.data_loader = data_loader
        self.schema_manager = schema_manager
        self.data_inserter = data_inserter
        self.analytics = analytics

    def run_analytics(self, students_file_path: Path, rooms_file_path: Path) -> None:
        connection = None
        try:
            students = self.data_loader.load_students(students_file_path)
            rooms = self.data_loader.load_rooms(rooms_file_path)

            connection = self.database_connection.connect()

            self.schema_manager.create_schema(connection)
            self.data_inserter.insert_rooms(connection, rooms)
            self.data_inserter.insert_students(connection, students)

            self._print_analytics_results(connection)

        except Exception as error:
            logger.exception("Application execution failed")
            raise
        finally:
            if connection and connection.is_connected():
                connection.close()
                logger.info("Database connection closed")

    def _print_analytics_results(self, connection: mysql.connector.MySQLConnection) -> None:
        print("\n=== Rooms and Student Count ===")
        rooms_with_count = self.analytics.get_rooms_with_student_count(connection)
        for room in rooms_with_count:
            print(f" {room['name']}: {room['student_count']} students")

        print("\n=== Top 5 Rooms with Smallest Average Age ===")
        top_avg_age = self.analytics.get_top_rooms_by_avg_age(connection, 5)
        for room in top_avg_age:
            print(f" {room['name']}: {room['avg_age']:.2f} years average")

        print("\n=== Top 5 Rooms with Largest Age Difference ===")
        top_age_diff = self.analytics.get_top_rooms_by_age_difference(connection, 5)
        for room in top_age_diff:
            print(f" {room['name']}: {room['age_difference']:.2f} years difference")

        print("\n=== Rooms with Mixed Genders ===")
        mixed_rooms = self.analytics.get_mixed_gender_rooms(connection)
        for room in mixed_rooms:
            print(f" {room['name']}: Mixed gender")


def main():
    database_config = {
        'host': 'localhost',
        'user': 'student_user',
        'password': 'student_password',
        'database': 'student_analytics'
    }

    database_connection = MySQLDatabaseConnection(**database_config)
    data_loader = JSONDataLoader()
    schema_manager = MySQLSchemaManager()
    data_inserter = MySQLDataInserter()
    analytics = StudentRoomAnalytics()

    app = StudentRoomAnalyticsApplication(
        database_connection,
        data_loader,
        schema_manager,
        data_inserter,
        analytics
    )

    students_file = Path('students.json')
    rooms_file = Path('rooms.json')

    app.run_analytics(students_file, rooms_file)


if __name__ == "__main__":
    main()