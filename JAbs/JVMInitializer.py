import typing
from abc import ABC, abstractmethod
from collections import OrderedDict
from os import pathsep as PATH_sep
from pathlib import Path

ClassesImportSpecT = typing.Union[typing.Iterable[str], typing.Mapping[str, str]]
ClassPathT = typing.Iterable[typing.Union[Path, str]]


def dedupPreservingOrder(*args: typing.Iterable[ClassPathT]) -> ClassPathT:
	dedup = OrderedDict()
	for col in args:
		if col:
			for el in col:
				dedup[el] = True

	return dedup.keys()


def normalizeClassPaths(classPaths: ClassPathT) -> ClassPathT:
	for f in classPaths:
		if isinstance(f, Path):
			f = str(f.absolute())
		yield f


def appendClassPath(classPaths: ClassPathT, origClassPath: typing.Iterable[str] = ()):
	classPaths = list(classPaths)
	res = dedupPreservingOrder(list(normalizeClassPaths(classPaths)), origClassPath)
	return res


def classPaths2String(classPaths):
	return PATH_sep.join(normalizeClassPaths(classPaths))


class JVMInitializer(ABC):
	#__slots__ = ("sys", )  # we inject loaded classes right into this class

	classPathPropertyName = "sys.class.path"
	classPathPropertyName = "java.class.path"  # new

	def __init__(self, classPathz: ClassPathT, classes2import: ClassesImportSpecT) -> None:
		self.prepareJVM()
		self.sys = self.loadClass("java.lang.System")
		classPathz = list(classPathz)
		self.appendClassPath(classPathz)
		self.loadClasses(classes2import)

	class _Implements(type):
		"""Used as a metaclass to wrap python classes implementing interfaces defined in JVM code"""
		__slots__ = ()

	def _Override(self, meth: typing.Callable) -> typing.Callable:
		"""Used as a decorator to wrap python methods overriding methods defined in JVM code"""
		return meth

	@abstractmethod
	def selectJVM(self) -> Path:
		"""Returns Path to libjvm.so"""
		raise NotImplementedError()

	@abstractmethod
	def prepareJVM(self):
		"""Starts JVM and sets its settings"""
		raise NotImplementedError()

	def reflClass2Class(self, cls) -> typing.Any:  # pylint: disable=no-self-use
		"""Transforms a reflection object for a class into an object usable by python"""
		return cls

	def reflectClass(self, cls) -> typing.Any:
		"""Transforms a a class into a reflection object for a class"""
		raise NotImplementedError

	@abstractmethod
	def loadClass(self, name: str) -> typing.Any:
		"""Returns a class"""
		raise NotImplementedError()

	@property
	def classPathStr(self) -> str:
		"""classpath string"""
		return str(self.sys.getProperty(self.__class__.classPathPropertyName))

	@classPathStr.setter
	def classPathStr(self, classPath: str) -> None:
		self.sys.setProperty(self.__class__.classPathPropertyName, classPath)

	@property
	def classPath(self) -> typing.Iterable[str]:
		"""classpath string separated into paths"""
		cps = self.classPathStr.split(PATH_sep)

		res = [None] * len(cps)
		for i, p in enumerate(cps):
			try:
				res[i] = Path(p)
			except BaseException:
				res[i] = p
		return tuple(res)

	@classPath.setter
	def classPath(self, classPaths: ClassPathT) -> None:
		self.classPathStr = classPaths2String(classPaths)

	def appendClassPath(self, classPaths: ClassPathT) -> None:
		"""Adds a jar into classpath"""
		self.classPath = appendClassPath(classPaths, self.classPath)

	def loadClasses(self, classes2import: ClassesImportSpecT) -> None:
		"""Loads the classes that are required to be loaded and injects them into `self`, using the last component of a path as a property"""
		if isinstance(classes2import, (list, tuple)):
			newSpec = {}
			for el in classes2import:
				if isinstance(el, tuple):
					name = el[1]
					path = el[0]
				else:
					name = el.split(".")[-1]
					path = el

				newSpec[name] = path

			classes2import = newSpec

			for k, className in newSpec.items():
				setattr(self, k, self.loadClass(className))
		else:
			raise ValueError("`classes2import` have wrong type", classes2import)
