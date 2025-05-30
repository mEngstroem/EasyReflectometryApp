from typing import List
from typing import Optional

from easyreflectometry import Project as ProjectLib
from PySide6.QtCore import Property
from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot

from .logic.calculators import Calculators as CalculatorsLogic
from .logic.experiments import Experiments as ExperimentLogic
from .logic.fitting import Fitting as FittingLogic
from .logic.minimizers import Minimizers as MinimizersLogic
from .logic.parameters import Parameters as ParametersLogic


class Analysis(QObject):
    minimizerChanged = Signal()
    calculatorChanged = Signal()
    experimentsChanged = Signal()
    parametersChanged = Signal()
    parametersIndexChanged = Signal()
    fittingChanged = Signal()

    externalMinimizerChanged = Signal()
    externalParametersChanged = Signal()
    externalCalculatorChanged = Signal()
    externalFittingChanged = Signal()

    def __init__(self, project_lib: ProjectLib, parent=None):
        super().__init__(parent)
        self._paramters_logic = ParametersLogic(project_lib)
        self._fitting_logic = FittingLogic(project_lib)
        self._calculators_logic = CalculatorsLogic(project_lib)
        self._experiments_logic = ExperimentLogic(project_lib)
        self._minimizers_logic = MinimizersLogic(project_lib)
        self._chached_paramters = None

    ########################
    ## Fitting
    @Property(str, notify=fittingChanged)
    def fittingStatus(self) -> str:
        return self._fitting_logic.status

    @Property(bool, notify=fittingChanged)
    def fittingRunning(self) -> bool:
        return self._fitting_logic.running

    @Property(bool, notify=fittingChanged)
    def isFitFinished(self) -> bool:
        return self._fitting_logic.fit_finished

    @Slot(None)
    def fittingStartStop(self) -> None:
        self._fitting_logic.start_stop()
        self.fittingChanged.emit()
        self._clearCacheAndEmitParametersChanged()
        self.externalFittingChanged.emit()

    ########################
    ## Calculators
    @Property('QVariantList', notify=calculatorChanged)
    def calculatorsAvailable(self) -> List[str]:
        return self._calculators_logic.available()

    @Property(int, notify=calculatorChanged)
    def calculatorCurrentIndex(self) -> int:
        return self._calculators_logic.current_index()

    @Slot(int)
    def setCalculatorCurrentIndex(self, new_value: int) -> None:
        if self._calculators_logic.set_current_index(new_value):
            self.calculatorChanged.emit()
            self.externalCalculatorChanged.emit()

    ########################
    ## Experiments
    @Property('QVariantList', notify=experimentsChanged)
    def experimentsAvailable(self) -> List[str]:
        return self._experiments_logic.available()

    @Property(int, notify=experimentsChanged)
    def experimentCurrentIndex(self) -> int:
        return self._experiments_logic.current_index()

    @Slot(int)
    def setExperimentCurrentIndex(self, new_value: int) -> None:
        self._experiments_logic.set_current_index(new_value)

    ########################
    ## Minimizers
    @Property('QVariantList', notify=minimizerChanged)
    def minimizersAvailable(self) -> List[str]:
        return self._minimizers_logic.minimizers_available()

    @Property(int, notify=minimizerChanged)
    def minimizerCurrentIndex(self) -> int:
        return self._minimizers_logic.minimizer_current_index()

    @Slot(int)
    def setMinimizerCurrentIndex(self, new_value: int) -> None:
        if self._minimizers_logic.set_minimizer_current_index(new_value):
            self.minimizerChanged.emit()
            self.externalMinimizerChanged.emit()

    @Property('QVariant', notify=minimizerChanged)
    def minimizerTolerance(self) -> Optional[float]:
        return self._minimizers_logic.tolerance

    @Property('QVariant', notify=minimizerChanged)
    def minimizerMaxIterations(self) -> Optional[int]:
        return self._minimizers_logic.max_iterations

    @Slot(float)
    def setMinimizerTolerance(self, new_value: float) -> None:
        if self._minimizers_logic.set_tolerance(new_value):
            self.minimizerChanged.emit()

    @Slot(int)
    def setMinimizerMaxIterations(self, new_value: int) -> None:
        if self._minimizers_logic.set_max_iterations(new_value):
            self.minimizerChanged.emit()

    #############
    ## Parameters
    @Property('QVariantList', notify=parametersChanged)
    def fitableParameters(self) -> List[dict[str]]:
        if self._chached_paramters is None:
            self._chached_paramters = self._paramters_logic.parameters
        return self._chached_paramters

    @Property(int, notify=parametersIndexChanged)
    def currentParameterIndex(self) -> int:
        return self._paramters_logic.current_index()

    @Slot(int)
    def setCurrentParameterIndex(self, new_value: int) -> None:
        if self._paramters_logic.set_current_index(new_value):
            self.parametersIndexChanged.emit()

    @Property(int, notify=parametersChanged)
    def freeParametersCount(self) -> int:
        return self._paramters_logic.count_free_parameters()

    @Property(int, notify=parametersChanged)
    def fixedParametersCount(self) -> int:
        return self._paramters_logic.count_fixed_parameters()

    @Property(int, notify=parametersChanged)
    def modelParametersCount(self) -> int:
        return 3

    @Property(int, notify=parametersChanged)
    def experimentParametersCount(self) -> int:
        return 3

    @Slot(float)
    def setCurrentParameterValue(self, new_value: float) -> None:
        if self._paramters_logic.set_current_parameter_value(new_value):
            self._clearCacheAndEmitParametersChanged()
            self.externalParametersChanged.emit()

    @Slot(float)
    def setCurrentParameterMin(self, new_value: float) -> None:
        if self._paramters_logic.set_current_parameter_min(new_value):
            self._clearCacheAndEmitParametersChanged()

    @Slot(float)
    def setCurrentParameterMax(self, new_value: float) -> None:
        if self._paramters_logic.set_current_parameter_max(new_value):
            self._clearCacheAndEmitParametersChanged()

    @Slot(bool)
    def setCurrentParameterFit(self, new_value: bool) -> None:
        if self._paramters_logic.set_current_parameter_fit(new_value):
            self._clearCacheAndEmitParametersChanged()

    def _clearCacheAndEmitParametersChanged(self):
        self._chached_paramters = None
        self.parametersChanged.emit()
