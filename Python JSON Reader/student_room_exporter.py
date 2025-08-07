import argparse
import json
import logging
import xml.etree.ElementTree as ET

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class Student(BaseModel):
    """Model representing a student with validation."""
    student_id: int = Field(alias="id", ge=0, description="Unique student identifier")
    name: str = Field(min_length=1, description="Student's full name")
    room: int = Field(ge=0, description="Room number assigned to student")

class Room(BaseModel):
    """Model representing a room with validation."""
    room_id: int = Field(alias="id", ge=0, description="Unique room identifier")
    name: str = Field(min_length=1, description="Room display name")
    students: list[Student] = Field(default_factory=list, description="Students assigned to this room")


class DataLoader:
    """Handles loading and parsing of JSON data files."""

    @staticmethod
    def load_students(file_path: Path) -> list[Student]:
        """
        Load and validate student data from JSON file.

        Args:
            file_path: Path to the students JSON file

        Returns:
            List of validated Student objects

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If JSON is invalid or data validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return [Student(**student_data) for student_data in data]
        except FileNotFoundError:
            raise FileNotFoundError(f"Students file not found: {file_path}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in students file: {error}")
        except ValidationError as e:
            raise ValueError(f"Invalid student data: {e}")

    @staticmethod
    def load_rooms(file_path: Path) -> list[Room]:
        """
        Load and validate room data from JSON file.

        Args:
            file_path: Path to the rooms JSON file

        Returns:
            List of validated Room objects

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If JSON is invalid or data validation fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return [Room(**room_data) for room_data in data]
        except FileNotFoundError:
            raise FileNotFoundError(f"Rooms file not found: {file_path}")
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in rooms file: {error}")
        except ValidationError as e:
            raise ValueError(f"Invalid room data: {e}")


class DataProcessor:
    """Processes and combines student and room data."""

    @staticmethod
    def combine_data(students: list[Student], rooms: list[Room]) -> list[Room]:
        """
        Combine students with their assigned rooms.

        Args:
            students: List of Student objects
            rooms: List of Room objects

        Returns:
            List of Room objects with assigned students
        """
        room_dict = {room.room_id: room for room in rooms}
        unassigned = []

        for student in students:
            if student.room in room_dict:
                room_dict[student.room].students.append(student)
            else:
                unassigned.append(student.student_id)

        if unassigned:
            logging.warning(f"Unassigned students (no matching room): {unassigned}")

        return list(room_dict.values())


class Exporter(ABC):
    """Abstract base class for data exporters."""

    @abstractmethod
    def export(self, data: list[Room], output_path: Path) -> None:
        """
        Export room data to specified format.

        Args:
            data: List of Room objects to export
            output_path: Path where to save the exported data
        """
        pass


class JSONExporter(Exporter):
    """Exports data to JSON format."""

    def export(self, data: list[Room], output_path: Path) -> None:
        """
        Export room data to JSON file.

        Args:
            data: List of Room objects to export
            output_path: Path where to save the JSON file
        """
        json_data = [self._room_to_dict(room) for room in data]

        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(json_data, file, indent=2, ensure_ascii=False)

    @staticmethod
    def _room_to_dict(room: Room) -> dict[str, Any]:
        """Convert Room object to dictionary for JSON serialization."""
        return {
            "id": room.room_id,
            "name": room.name,
            "students": [
                {
                    "id": student.student_id,
                    "name": student.name,
                    "room": student.room
                }
                for student in room.students
            ]
        }


class XMLExporter(Exporter):
    """Exports data to XML format."""

    def export(self, data: list[Room], output_path: Path) -> None:
        """
        Export room data to XML file.

        Args:
            data: List of Room objects to export
            output_path: Path where to save the XML file
        """
        root = ET.Element("rooms")

        for room in data:
            self._add_room_to_xml(root, room)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)

    @staticmethod
    def _add_room_to_xml(parent: ET.Element, room: Room) -> None:
        """Add Room data to XML element."""
        room_element = ET.SubElement(parent, "room")
        room_element.set("id", str(room.room_id))
        room_element.set("name", room.name)

        for student in room.students:
            student_element = ET.SubElement(room_element, "student")
            student_element.set("id", str(student.student_id))
            student_element.set("name", student.name)
            student_element.set("room", str(student.room))


class ExporterFactory:
    """Factory for creating appropriate exporter instances."""

    _exporters = {
        'json': JSONExporter,
        'xml': XMLExporter
    }

    @classmethod
    def create_exporter(cls, format_type: str) -> Exporter:
        """
        Create exporter instance based on format type.

        Args:
            format_type: Type of exporter ('json' or 'xml')

        Returns:
            Appropriate Exporter instance

        Raises:
            ValueError: If format type is not supported
        """
        exporter_class = cls._exporters.get(format_type.lower())
        if not exporter_class:
            supported_formats = ', '.join(cls._exporters.keys())
            raise ValueError(f"Unsupported format: {format_type}. "
                             f"Supported formats: {supported_formats}")
        return exporter_class()


class StudentRoomExporter:
    """Main application class that orchestrates the export process."""

    def __init__(self, data_loader: DataLoader, data_processor: DataProcessor):
        """
        Initialize the exporter with dependencies.

        Args:
            data_loader: Instance for loading data from files
            data_processor: Instance for processing and combining data
        """
        self.data_loader = data_loader
        self.data_processor = data_processor

    def export_data(self, students_file: Path, rooms_file: Path,
                    output_file: Path, export_format: str) -> None:
        """
        Main method to load, process, and export data.

        Args:
            students_file: Path to students JSON file
            rooms_file: Path to rooms JSON file
            output_file: Path for output file
            export_format: Output format ('json' or 'xml')
        """
        try:
            students = self.data_loader.load_students(students_file)
            rooms = self.data_loader.load_rooms(rooms_file)

            processed_rooms = self.data_processor.combine_data(students, rooms)

            exporter = ExporterFactory.create_exporter(export_format)
            exporter.export(processed_rooms, output_file)

            logging.info(f"Data successfully exported to {output_file}")

        except Exception as error:
            logging.error(f"Unexpected error: {error}")
            raise


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Export student-room data.")
    parser.add_argument("students_file", type=Path, help="Path to students.json")
    parser.add_argument("rooms_file", type=Path, help="Path to rooms.json")
    parser.add_argument("output_file", type=Path, help="Output file path")
    parser.add_argument("format", choices=["json", "xml"], help="Export format")
    args = parser.parse_args()

    if not args.output_file.suffix:
        extension = ".json" if args.format == "json" else ".xml"
        args.output_file = args.output_file.with_suffix(extension)
        logging.info(f"Appended extension: {args.output_file}")

    exporter = StudentRoomExporter(DataLoader(), DataProcessor())
    exporter.export_data(args.students_file, args.rooms_file, args.output_file, args.format)

if __name__ == "__main__":
    main()
