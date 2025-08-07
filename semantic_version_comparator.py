import functools
import re
from dataclasses import dataclass, field
from typing import ClassVar, Optional


@functools.total_ordering
@dataclass(frozen=True)
class Version:
    """
    A class representing a semantic version (SemVer) as specified in https://semver.org/.

    Supports parsing version strings and comparing versions according to SemVer rules.

    Examples:
        >>> Version('1.1.3') < Version('2.2.3')
        True
        >>> Version('1.3.0') > Version('0.3.0')
        True
        >>> Version('0.3.0b') < Version('1.2.42')
        True
        >>> Version('1.3.42') == Version('42.3.1')
        False
    """
    major: int
    minor: int
    patch: int
    prerelease: tuple[int | str, ...] = field(default_factory=tuple)
    buildmetadata: str = ""

    # Class-level regex for parsing semver strings
    _semver_regex: ClassVar[re.Pattern] = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>[0-9A-Za-z\-\.]+))?"
        r"(?:\+(?P<buildmetadata>[0-9A-Za-z\-\.]+))?$"
    )


    def __init__(self, version: str) -> None:
        """
        Initialize a Version object from a version string.

        Args:
            version: A string representing a semantic version (e.g., '1.2.3', '1.0.0-alpha')

        Raises:
            ValueError: If the version string is not a valid semantic version
        """
        # Using __setattr__ because the dataclass is frozen
        object.__setattr__(self, 'major', 0)
        object.__setattr__(self, 'minor', 0)
        object.__setattr__(self, 'patch', 0)
        object.__setattr__(self, 'prerelease', ())
        object.__setattr__(self, 'buildmetadata', "")

        match_result = self._semver_regex.match(version)
        if not match_result:
            # Handle versions like "1.2.3b" by converting to "1.2.3-b"
            alternative_version = re.sub(r"^(\d+\.\d+\.\d+)([a-zA-Z][a-zA-Z0-9]*)$", r"\1-\2", version)
            match_result = self._semver_regex.match(alternative_version)
            if not match_result:
                raise ValueError(
                    f"Invalid version: '{version}'. Expected format: X.Y.Z[-prerelease][+buildmetadata] "
                    f"where X, Y, Z are non-negative integers without leading zeros."
                )

        object.__setattr__(self, 'major', int(match_result.group("major")))
        object.__setattr__(self, 'minor', int(match_result.group("minor")))
        object.__setattr__(self, 'patch', int(match_result.group("patch")))
        object.__setattr__(self, 'prerelease', self._parse_prerelease(match_result.group("prerelease")))
        object.__setattr__(self, 'buildmetadata', match_result.group("buildmetadata") or "")

    @classmethod
    def from_parts(cls, major: int, minor: int, patch: int,
                   prerelease: Optional[tuple[int | str, ...]] = None,
                   buildmetadata: str = "") -> 'Version':
        """
        Create a Version object directly from its component parts, avoiding string parsing overhead.

        Args:
            major: Major version component
            minor: Minor version component
            patch: Patch version component
            prerelease: Optional prerelease identifiers
            buildmetadata: Optional build metadata

        Returns:
            A new Version instance

        Raises:
            ValueError: If version components are invalid (negative numbers)
        """
        if major < 0 or minor < 0 or patch < 0:
            raise ValueError("Version components must be non-negative")

        instance = cls.__new__(cls)
        object.__setattr__(instance, 'major', major)
        object.__setattr__(instance, 'minor', minor)
        object.__setattr__(instance, 'patch', patch)
        object.__setattr__(instance, 'prerelease', prerelease if prerelease is not None else ())
        object.__setattr__(instance, 'buildmetadata', buildmetadata)
        return instance

    def _parse_prerelease(self, prerelease_string: Optional[str]) -> tuple[int | str, ...]:
        """
        Parse the prerelease component of a version string.

        Args:
            prerelease_string: The prerelease string, like 'alpha.1'

        Returns:
            A tuple of prerelease identifiers, with numeric identifiers as integers

        Raises:
            ValueError: If prerelease identifiers are invalid
        """
        if not prerelease_string:
            return ()

        prerelease_parts = prerelease_string.split('.')
        parsed_identifiers = []
        for identifier in prerelease_parts:
            # Validate according to SemVer: identifiers must be non-empty
            if not identifier:
                raise ValueError("Prerelease identifiers must be non-empty")

            # Numeric identifiers must not have leading zeros
            if identifier.isdigit():
                if identifier.startswith('0') and len(identifier) > 1:
                    raise ValueError(f"Numeric prerelease identifier '{identifier}' must not have leading zeros")
                parsed_identifiers.append(int(identifier))
            else:
                # Validate: only alphanumeric and hyphen allowed in identifiers
                if not all(character.isalnum() or character == '-' for character in identifier):
                    raise ValueError(f"Invalid prerelease identifier '{identifier}'")
                parsed_identifiers.append(identifier)

        return tuple(parsed_identifiers)

    def __str__(self) -> str:
        """Return the string representation of the version."""
        base_version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            prerelease_string = ".".join(str(identifier) for identifier in self.prerelease)
            base_version += f"-{prerelease_string}"
        if self.buildmetadata:
            base_version += f"+{self.buildmetadata}"
        return base_version

    def __eq__(self, other: object) -> bool:
        """
        Compare equality of two versions according to SemVer rules.
        Build metadata is ignored in comparisons.
        """
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch and
                self.prerelease == other.prerelease)

    def __lt__(self, other: object) -> bool:
        """
        Compare versions according to SemVer precedence rules.
        Precedence is determined by the first difference when comparing:
        1. Major version
        2. Minor version
        3. Patch version
        4. A version with a prerelease has lower precedence than one without
        5. Prerelease identifiers are compared numerically/lexically
        """
        if not isinstance(other, Version):
            return NotImplemented

        # Compare major.minor.patch
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch

        # Version with prerelease has lower precedence than without
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and not other.prerelease:
            return True

        # Compare prerelease identifiers
        for self_identifier, other_identifier in zip(self.prerelease, other.prerelease):
            # If types differ, numeric identifiers have lower precedence
            if isinstance(self_identifier, int) and isinstance(other_identifier, str):
                return True
            if isinstance(self_identifier, str) and isinstance(other_identifier, int):
                return False

            # If same type, compare directly
            if self_identifier != other_identifier:
                return self_identifier < other_identifier

        # If all common identifiers are equal, shorter list has lower precedence
        return len(self.prerelease) < len(other.prerelease)

    def __hash__(self) -> int:
        """
        Return a hash value for the version, ignoring build metadata.
        Enables use in sets and as dictionary keys for fast lookups.
        """
        return hash((self.major, self.minor, self.patch, self.prerelease))


def main() -> None:
    to_test = [
        ("1.0.0", "2.0.0"),
        ("1.0.0", "1.42.0"),
        ("1.2.0", "1.2.42"),
        ("1.1.0-alpha", "1.2.0-alpha.1"),
        ("1.0.1b", "1.0.10-alpha.beta"),
        ("1.0.0-rc.1", "1.0.0"),
    ]

    for left, right in to_test:
        assert Version(left) < Version(right), f"'{left}' < '{right}' failed"
        assert Version(right) > Version(left), f"'{right}' > '{left}' failed"
        assert Version(right) != Version(left), f"'{right}' != '{left}' failed"

    # Additional tests
    assert Version("1.1.3") < Version("2.2.3")
    assert Version("1.3.0") > Version("0.3.0")
    assert Version("0.3.0b") < Version("1.2.42")
    assert Version("1.3.42") != Version("42.3.1")

    # Test from_parts
    v1 = Version.from_parts(1, 2, 3, ("alpha", 1))
    v2 = Version("1.2.3-alpha.1")
    assert v1 == v2, "from_parts constructor failed"

    # Test hash functionality for sets
    version_set = {Version("1.0.0"), Version("1.0.0")}
    assert len(version_set) == 1, "Hashing failed for set deduplication"

    print("All tests passed successfully!")


if __name__ == "__main__":
    main()