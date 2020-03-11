__all__ = ("extractClassesFromAJar",)

from pathlib import Path
import zipfile


def _extractClassesFromAJar(jarPath: Path) -> typing.Iterator[typing.Tuple[str, ...]]:
	classExt = ".class"
	with zipfile.ZipFile(jarPath) as z:
		for f in z.infolist():
			if f.filename.endswith(classExt):
				path = PurePath(f.filename)
				yield path.parts[:-1] + (path.stem,)


def extractClassesFromAJar(jarPath: Path) -> typing.Any:
	return tuple(sorted(_extractClassesFromAJar(jarPath)))
