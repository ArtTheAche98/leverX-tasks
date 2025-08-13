from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Protocol

import json
import xml.etree.ElementTree as ET
import logging.config
import click

from dataclasses import dataclass, field
from typing import Dict, Any

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@dataclass
class Student:
    """Represents a student with ID, name, and assigned room number."""
    id: int
    name: str
    room: int


@dataclass
class Room:
    """Represents a room with ID, name, and list of assigned students."""
    id: int
    name: str
    students: List[Student] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert room to dictionary for export."""
        return {
            "id": self.id,
            "name": self.name,
            "students": [
                {"id": s.id, "name": s.name, "room": s.room}
                for s in self.students
            ]
        }


class DataLoaderProtocol(Protocol):
    """Protocol defining the interface for data loading operations."""

    def load_students(self, file_path: Path) -> List[Student]:
        """Load students from file."""
        ...

    def load_rooms(self, file_path: Path) -> List[Room]:
        """Load rooms from file."""
        ...


class StudentRoomAggregatorProtocol(Protocol):
    """Protocol defining the interface for combining student and room data."""

    def aggregate_students_to_rooms(self, students: List[Student], rooms: List[Room]) -> List[Room]:
        """Combine students with their assigned rooms."""
        ...


class DataExporterProtocol(Protocol):
    """Protocol defining the interface for data export operations."""

    def export(self, rooms: List[Room], output_path: Path) -> None:
        """Export rooms data to specified path."""
        ...


class JSONDataLoader:
    """Loads student and room data from JSON files."""

    def load_students(self, file_path: Path) -> List[Student]:
        """Load and validate student data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Student file not found: {file_path}")

        try:
            return [
                Student(id=item["id"], name=item["name"], room=item["room"])
                for item in data
            ]
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid student data structure: {e}")

    def load_rooms(self, file_path: Path) -> List[Room]:
        """Load and validate room data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Room file not found: {file_path}")

        try:
            return [
                Room(id=item["id"], name=item["name"])
                for item in data
            ]
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid room data structure: {e}")


class StudentRoomAggregator:
    """Combines student data with room assignments."""

    def aggregate_students_to_rooms(self, students: List[Student], rooms: List[Room]) -> List[Room]:
        """Assign students to their corresponding rooms and log unassigned students."""
        room_map = {room.id: room for room in rooms}
        unassigned_students = []

        for student in students:
            if student.room in room_map:
                room_map[student.room].students.append(student)
            else:
                unassigned_students.append(student)

        if unassigned_students:
            logger.warning(
                "Unassigned students found: %s",
                [f"{s.name} (room {s.room})" for s in unassigned_students]
            )

        return rooms


class JSONExporter:
    """Exports room data to JSON format."""

    def export(self, rooms: List[Room], output_path: Path) -> None:
        """Export rooms data to JSON file."""
        try:
            data = [room.to_dict() for room in rooms]
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            logger.info("Successfully exported data to %s", output_path)
        except Exception as e:
            logger.exception("Failed to export to JSON")
            raise


class XMLExporter:
    """Exports room data to XML format."""

    def export(self, rooms: List[Room], output_path: Path) -> None:
        """Export rooms data to XML file."""
        try:
            root = ET.Element("rooms")

            for room in rooms:
                room_elem = ET.SubElement(root, "room")
                room_elem.set("id", str(room.id))
                room_elem.set("name", room.name)

                for student in room.students:
                    student_elem = ET.SubElement(room_elem, "student")
                    student_elem.set("id", str(student.id))
                    student_elem.set("name", student.name)
                    student_elem.set("room", str(student.room))

            tree = ET.ElementTree(root)
            tree.write(output_path, encoding="utf-8", xml_declaration=True)
            logger.info("Successfully exported data to %s", output_path)
        except Exception as e:
            logger.exception("Failed to export to XML")
            raise


class ExporterFactory:
    """Factory for creating appropriate data exporters."""

    @staticmethod
    def create_exporter(export_format: str) -> DataExporterProtocol:
        """Create exporter based on specified format."""
        exporters = {
            "json": JSONExporter,
            "xml": XMLExporter
        }

        if export_format not in exporters:
            raise ValueError(f"Unsupported format: {export_format}. Supported: {list(exporters.keys())}")

        return exporters[export_format]()


class StudentRoomExporter:
    """Main class orchestrating the student-room data export process."""

    def __init__(
            self,
            data_loader: DataLoaderProtocol,
            aggregator: StudentRoomAggregatorProtocol
    ):
        self.data_loader = data_loader
        self.aggregator = aggregator

    def export_data(
            self,
            students_path: Path,
            rooms_path: Path,
            output_path: Path,
            export_format: str
    ) -> None:
        """Complete export workflow: load, process, and export data."""
        try:
            logger.info("Starting data export process")

            students = self.data_loader.load_students(students_path)
            rooms = self.data_loader.load_rooms(rooms_path)

            logger.info("Loaded %d students and %d rooms", len(students), len(rooms))

            processed_rooms = self.aggregator.aggregate_students_to_rooms(students, rooms)

            exporter = ExporterFactory.create_exporter(export_format)
            exporter.export(processed_rooms, output_path)

            logger.info("Export process completed successfully")

        except Exception as e:
            logger.exception("Export process failed")
            raise


class CLIApplication:
    """Command line interface for the student room exporter."""

    def __init__(self):
        self.exporter = StudentRoomExporter(
            JSONDataLoader(),
            StudentRoomAggregator()
        )

    def run(self) -> None:
        """Set up and run the CLI application."""

        @click.command()
        @click.argument('students_file', type=click.Path(exists=True, path_type=Path))
        @click.argument('rooms_file', type=click.Path(exists=True, path_type=Path))
        @click.argument('output_file', type=click.Path(path_type=Path))
        @click.option(
            '--format',
            type=click.Choice(['json', 'xml'], case_sensitive=False),
            required=True,
            help='Output format (json or xml)'
        )
        def export_command(
                students_file: Path,
                rooms_file: Path,
                output_file: Path,
                format: str
        ) -> None:
            """Export student room assignments to specified format.

            STUDENTS_FILE: Path to JSON file containing student data
            ROOMS_FILE: Path to JSON file containing room data  
            OUTPUT_FILE: Path for the exported output file

            Example:
                python student_room_exporter.py students.json rooms.json output.json --format json
             OR
                python student_room_exporter.py students.json rooms.json output.xml --format xml
            """
            try:
                self.exporter.export_data(
                    students_file,
                    rooms_file,
                    output_file,
                    format.lower()
                )
            except Exception as e:
                logger.exception("Application failed")
                raise click.ClickException(f"Export failed: {e}")

        export_command()


def main() -> None:
    """Entry point for the application."""
    app = CLIApplication()
    app.run()


if __name__ == "__main__":
    main()