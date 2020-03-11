from pathlib import Path
import java  # pylint: disable=import-error

from ..JVMInitializer import JVMInitializer


class GraalVMInitializer(JVMInitializer):
	__slots__ = ("ClassLoader", "_systemClassLoader")

	def prepareJVM(self):
		self.ClassLoader = java.type("java.lang.ClassLoader")
		self._systemClassLoader = self.ClassLoader.getSystemClassLoader()

	def selectJVM(self) -> Path:  # pylint: disable=no-self-use
		return None

	def loadClass(self, name: str):
		return self._systemClassLoader.loadClass(name)


SelectedJVMInitializer = GraalVMInitializer
