import json
import logging
import pytest

from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, mock_open
from pydantic import ValidationError

import xml.etree.ElementTree as ET

from hypothesis import given, strategies as st

from student_room_exporter import (
    Student, Room, StudentRoomExporter, DataLoader, DataProcessor,
    ExporterFactory, JSONExporter, XMLExporter
)


@pytest.fixture
def sample_student() -> Student:
    """Fixture for a sample valid Student using alias construction."""
    return Student.model_validate({"id": 1, "name": "Test Student", "room": 1})


@pytest.fixture
def sample_room() -> Room:
    """Fixture for a sample valid Room using alias construction."""
    return Room.model_validate({"id": 1, "name": "Test Room"})


@pytest.fixture
def exporter() -> Generator[StudentRoomExporter, None, None]:
    """Fixture providing a mocked StudentRoomExporter instance for isolated testing."""
    loader = MagicMock(spec=DataLoader)
    processor = MagicMock(spec=DataProcessor)
    yield StudentRoomExporter(loader, processor)


class TestStudentRoomExporter:
    """Tests for StudentRoomExporter class."""

    def test_export_data_success(self, exporter: StudentRoomExporter) -> None:
        """Test successful execution of export_data with mocked dependencies."""
        exporter.data_loader.load_students.return_value = [
            Student.model_validate({"id": 1, "name": "Test Student", "room": 1})]
        exporter.data_loader.load_rooms.return_value = [Room.model_validate({"id": 1, "name": "Test Room"})]
        exporter.data_processor.combine_data.return_value = [Room.model_validate({"id": 1, "name": "Test Room"})]

        with patch('student_room_exporter.ExporterFactory.create_exporter') as mock_factory:
            mock_exporter = MagicMock()
            mock_factory.return_value = mock_exporter
            exporter.export_data(Path("students.json"), Path("rooms.json"), Path("output.json"), "json")
            mock_exporter.export.assert_called_once()

    def test_export_data_validation_error(self, exporter: StudentRoomExporter) -> None:
        """Test handling of validation errors during data loading."""
        exporter.data_loader.load_students.side_effect = ValueError("Invalid student data")
        with pytest.raises(ValueError):
            exporter.export_data(Path("invalid.json"), Path("rooms.json"), Path("output.json"), "json")

    def test_export_data_file_not_found(self, exporter: StudentRoomExporter) -> None:
        """Test handling of file not found errors during loading."""
        exporter.data_loader.load_rooms.side_effect = FileNotFoundError("File not found")
        with pytest.raises(FileNotFoundError):
            exporter.export_data(Path("students.json"), Path("missing.json"), Path("output.xml"), "xml")


class TestDataLoader:
    """Tests for DataLoader class."""

    def test_load_students_success(self) -> None:
        """Test successful student loading."""
        student_data = json.dumps([{"id": 1, "name": "Test", "room": 1}])
        loader = DataLoader()
        with patch("builtins.open", mock_open(read_data=student_data)):
            students = loader.load_students(Path("test.json"))
            assert len(students) == 1
            assert students[0].name == "Test"

    def test_load_students_invalid_json(self) -> None:
        """Test DataLoader with malformed JSON."""
        loader = DataLoader()
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with pytest.raises(ValueError, match="Invalid JSON"):
                loader.load_students(Path("invalid.json"))

    def test_load_students_validation_error(self) -> None:
        """Test DataLoader with invalid data structure."""
        loader = DataLoader()
        invalid_data = json.dumps([{"invalid": "field"}])
        with patch("builtins.open", mock_open(read_data=invalid_data)):
            with pytest.raises(ValueError, match="Invalid student data"):
                loader.load_students(Path("test.json"))


class TestDataProcessor:
    """Tests for DataProcessor class."""

    def test_combine_data_multiple_students_per_room(self, sample_student: Student, sample_room: Room) -> None:
        """Test combining multiple students in same room."""
        students = [
            sample_student,
            Student.model_validate({"id": 2, "name": "Bob", "room": 1})
        ]
        rooms = [sample_room]
        processor = DataProcessor()
        result = processor.combine_data(students, rooms)
        assert len(result[0].students) == 2

    def test_combine_data_empty_inputs(self) -> None:
        """Test combine_data with empty inputs."""
        processor = DataProcessor()
        result = processor.combine_data([], [])
        assert result == []

    def test_combine_data_unassigned_students(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging of unassigned students in combine_data."""
        processor = DataProcessor()
        students = [Student.model_validate({"id": 2, "name": "Unassigned", "room": 999})]
        rooms = [Room.model_validate({"id": 1, "name": "Room1"})]
        with caplog.at_level(logging.WARNING):
            processor.combine_data(students, rooms)
            assert "Unassigned students" in caplog.text

    @given(
        num_students=st.integers(min_value=0, max_value=100),
        num_rooms=st.integers(min_value=0, max_value=10)
    )
    def test_combine_data_property_based(self, num_students: int, num_rooms: int) -> None:
        """Property-based test: Number of assigned students <= total students."""
        processor = DataProcessor()
        students = [
            Student.model_validate({"id": i, "name": f"S{i}", "room": i % (num_rooms + 1)})
            for i in range(num_students)
        ]
        rooms = [
            Room.model_validate({"id": i, "name": f"R{i}"})
            for i in range(num_rooms)
        ]
        result = processor.combine_data(students, rooms)
        assigned_count = sum(len(r.students) for r in result)
        assert assigned_count <= num_students

    def test_combine_data_performance(self, benchmark) -> None:
        """Benchmark combine_data with large input."""
        processor = DataProcessor()
        students = [
            Student.model_validate({"id": i, "name": f"Student {i}", "room": 1})
            for i in range(10000)
        ]
        rooms = [Room.model_validate({"id": 1, "name": "Large Room"})]
        benchmark(processor.combine_data, students, rooms)


class TestExporters:
    """Tests for exporter classes and factory."""

    def test_exporter_factory_invalid_format(self) -> None:
        """Test ExporterFactory with unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            ExporterFactory.create_exporter("unsupported")

    @pytest.mark.parametrize("export_format,expected_exporter", [
        ("json", JSONExporter),
        ("xml", XMLExporter)
    ])
    def test_factory_creates_correct_exporter(self, export_format: str, expected_exporter) -> None:
        """Test factory creates the correct exporter type."""
        exporter = ExporterFactory.create_exporter(export_format)
        assert isinstance(exporter, expected_exporter)

    def test_json_export_special_characters(self) -> None:
        """Test JSON export handles special characters properly."""
        room = Room.model_validate({"id": 1, "name": "Room \"Test\""})
        student = Student.model_validate({"id": 1, "name": "Alice & Bob", "room": 1})
        room.students = [student]
        rooms = [room]

        exporter = JSONExporter()
        with patch("builtins.open", mock_open()) as mock_file:
            exporter.export(rooms, Path("test.json"))
            handle = mock_file()
            written = ''.join(call.args[0] for call in handle.write.call_args_list)
            data = json.loads(written)
            assert data[0]["name"] == "Room \"Test\""
            assert data[0]["students"][0]["name"] == "Alice & Bob"

    def test_xml_export_special_characters(self) -> None:
        """Test XML export handles special characters properly."""
        room = Room.model_validate({"id": 1, "name": "Room & <Test>"})
        student = Student.model_validate({"id": 1, "name": "Alice & Bob", "room": 1})
        room.students = [student]

        exporter = XMLExporter()
        with patch("builtins.open", mock_open()) as mock_file:
            exporter.export([room], Path("test.xml"))
            written_xml = ''.join(call.args[0] for call in mock_file().write.call_args_list)
            root = ET.fromstring(written_xml)
            assert root.find("room").get("name") == "Room & <Test>"

    def test_json_export_empty_rooms(self) -> None:
        """Test JSON export with empty room list."""
        exporter = JSONExporter()
        with patch("builtins.open", mock_open()) as mock_file:
            exporter.export([], Path("empty.json"))
            handle = mock_file()
            written = ''.join(call.args[0] for call in handle.write.call_args_list)
            assert json.loads(written) == []


def test_end_to_end_integration(tmp_path: Path) -> None:
    """Integration test: Complete workflow with temporary files."""
    students_path = tmp_path / "students.json"
    rooms_path = tmp_path / "rooms.json"
    output_path = tmp_path / "output.json"

    students_data = [{"id": 1, "name": "Alice", "room": 1}]
    rooms_data = [{"id": 1, "name": "Room1"}]

    students_path.write_text(json.dumps(students_data))
    rooms_path.write_text(json.dumps(rooms_data))

    exporter = StudentRoomExporter(DataLoader(), DataProcessor())
    exporter.export_data(students_path, rooms_path, output_path, "json")

    output_data = json.loads(output_path.read_text())
    assert output_data[0]["name"] == "Room1"
    assert output_data[0]["students"][0]["name"] == "Alice"