import typing
import warnings
from pathlib import PurePath, Path
import zipfile
from collections import defaultdict

import _jpype
import jpype
import jpype.beans

from ..JVMInitializer import JVMInitializer, ClassPathT, ClassesImportSpecT

ji = None

class RootClassLoaderWrapper:
	__slots__ = ("cl", "children")

	def __init__(self, cl):
		self.cl = cl
		self.children = {}

	def free(self):
		del self.cl

class ClassLoaderWrapper(RootClassLoaderWrapper):
	__slots__ = ("cl", "children", "parent")

	def __init__(self, cl, parent):
		super().__init__(cl)
		self.parent = parent
		parent.children[id(cl)] = self

	def free(self):
		if self.children:
			raise ValueError("Cannot free a loader with children")

		del self.parent[id(self.cl)]
		super().free()

class _JPypeInitializer(JVMInitializer):
	__slots__ = ("_allowShutdown",)
	classPathPropertyName = "java.class.path"

	def __init__(self, classPathz: ClassPathT, classes2import: ClassesImportSpecT, *, _allowShutdown: bool = False) -> None:
		self._allowShutdown = _allowShutdown
		if _allowShutdown:
			warnings.warn("`_allowShutdown` was used to allow `jpype.shutdownJVM`. See https://jpype.readthedocs.io/en/latest/userguide.html#unloading-the-jvm and https://github.com/jpype-project/jpype/blob/master/native/common/jp_context.cpp#L290")

		# these ones are defered. Before JVM is initialized they are accumulated by JPipe itself. They are not the same as loaded in runtime. Ones loaded in runtime may have various conflicts because of different classloaders.
		for cp in classPathz:
			jpype._classpath.addClassPath(cp.absolute())

		# because JPype accumulates them itself, we put here nothing
		super().__init__([], classes2import)

	def selectJVM(self) -> Path:
		return Path(jpype.getDefaultJVMPath())

	@property
	def classPath(self) -> typing.Iterable[str]:
		return tuple(self._loadedJars)

	@classPath.setter
	def classPath(self, classPath: ClassPathT) -> None:
		raise NotImplementedError("For this backend redefining classpath is not supported, use `appendClassPath`")

	def appendClassPath(self, classPaths: ClassPathT) -> None:
		"""JPype has adding jars into a classpath in runtime broken. So here is our surrogate. This function will load a jar using `java.net.URLClassLoader`. It would store loaders in a map keyed by a package name, so classes can be retrieved in 2 steps implemeted in `_trySearchLoadedInRuntime`."""

		for cp in classPaths:
			jpype._classpath.addClassPath(cp.absolute())

	def loadClass(self, name: str):
		res = jpype.JClass(name)

		assert isinstance(res, jpype._jpype._JClass), "Class `" + repr(name) + "` is not loaded (res.__class__ == " + repr(res.__class__) + "), it's JPype drawback that when something is missing it returns a `jpype._jpackage.JPackage`, that errors only when one tries to instantiate it as a class"  # pylint: disable=c-extension-no-member,protected-access
		return res

	def reflClass2Class(self, cls) -> typing.Any:  # pylint: disable=no-self-use
		return jpype.types.JClass(cls)

	def prepareJVM(self) -> None:
		if jpype.isJVMStarted():
			warnings.warn("JPype disallows starting multiple JVMs or restarting it. Assuming that JVM is already started with needed arguments, such as classpath.")
			if not self._allowShutdown:
				return
			jpype.shutdownJVM()

		# WARNING
		# 1. sys.class.path doesn't work
		# 2. only classpath set via "-Djava.class.path=" takes effect, https://github.com/jpype-project/jpype/issues/177
		# 3. I have implemented loading of packages in runtime in https://github.com/jpype-project/jpype/pull/840
		jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", convertStrings=False, ignoreUnrecognized=False)

	def reflectClass(self, cls) -> typing.Any:
		return cls.class_

	@staticmethod
	def _Implements(className: str, parents: typing.Tuple[typing.Type, ...], attrs: typing.Dict[str, typing.Any]):
		interface = parents[0]
		res = type(className, (), attrs)
		dec = jpype.JImplements(interface)
		return dec(res)

	_Override = staticmethod(jpype.JOverride)

class JPypeInitializer(_JPypeInitializer):
	__slots__ = ("_allowShutdown", "_systemClassLoader", "_loadedPackages", "_loadedJars")
	classPathPropertyName = "java.class.path"

	def __new__(cls, classPathz: ClassPathT, classes2import: ClassesImportSpecT, *args, **kwargs):
		global ji
		if ji is None:
			ji = _JPypeInitializer(classPathz, classes2import, *args, **kwargs)
		else:
			ji.appendClassPath(classPathz)
			ji.loadClasses(classes2import)

		return ji


SelectedJVMInitializer = JPypeInitializer
