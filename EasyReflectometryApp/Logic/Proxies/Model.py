from dicttoxml import dicttoxml

from PySide2.QtCore import QObject, Signal, Property, Slot

from easyCore import np, borg
from easyCore.Utils.UndoRedo import property_stack_deco

from EasyReflectometry.sample.layer import Layer
from EasyReflectometry.sample.item import MultiLayer, RepeatingMultiLayer, SurfactantLayer
from EasyReflectometry.sample.structure import Structure
from EasyReflectometry.experiment.model import Model
from EasyReflectometry.interface import InterfaceFactory

ITEM_LOOKUP = {'Multi-layer': MultiLayer, 'Repeating Multi-layer': RepeatingMultiLayer, 'Surfactant Layer': SurfactantLayer}


class ModelProxy(QObject):

    modelChanged = Signal()
    modelNameChanged = Signal()

    modelAsXmlChanged = Signal()
    modelAsObjChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self._model_as_obj = []
        self._model_as_xml = ""
        self._structure = self._defaultStructure(interface=parent._interface)
        self._model = self._defaultModel(structure=self._structure, interface=parent._interface)

        self._current_layers_index = 1
        self._current_items_index = 1

        self.modelChanged.connect(self._onCurrentItemsChanged)

    # # #
    # Defaults
    # # #

    def _defaultStructure(self, interface=None) -> Structure:
        layers = [
            Layer.from_pars(self.parent._material_proxy._materials[0],
                            0.0,
                            0.0,
                            name='Vacuum Layer'),
            Layer.from_pars(self.parent._material_proxy._materials[1],
                            100.0,
                            3.0,
                            name='D2O Layer'),
            Layer.from_pars(self.parent._material_proxy._materials[2],
                            0.0,
                            1.2,
                            name='Si Layer'),
        ]
        items = [
            MultiLayer.from_pars(layers[0], name='Superphase'),
            MultiLayer.from_pars(layers[1], name='D2O Layer'),
            MultiLayer.from_pars(layers[2], name='Subphase')
        ]
        structure =  Structure.from_pars(*items) 
        structure[0].layers[0].thickness.enabled = False
        structure[0].layers[0].roughness.enabled = False
        structure[-1].layers[-1].thickness.enabled = False
        return structure

    def _defaultModel(self, structure: Structure, interface=None) -> Model:
        return Model.from_pars(structure, 1, 0, 0, interface=interface)

    # # #
    # Setters and getters
    # # #

    @Property('QVariant', notify=modelAsObjChanged)
    def modelAsObj(self):
        return self._model_as_obj

    def _setModelAsObj(self):
        self._model_as_obj = []
        for i in self._structure:
            dictionary = {'name': i.name}
            dictionary['type'] = i.type
            dictionary['layers'] = [j.as_dict(skip=['interface']) for j in i.layers]
            if 'repetitions' in dictionary.keys():
                dictionary['repetitions'] = i.repetitions.as_dict(skip=['interface'])
            self._model_as_obj.append(dictionary)
        if len(self._structure) > 0:
            self._model_as_obj[0]['layers'][0]['thickness']['value'] = np.nan
            self._model_as_obj[0]['layers'][0]['roughness']['value'] = np.nan
            self._model_as_obj[-1]['layers'][-1]['thickness']['value'] = np.nan
        self.modelAsObjChanged.emit()

    @Property(str, notify=modelAsXmlChanged)
    def modelAsXml(self):
        return self._model_as_xml

    @modelAsXml.setter
    @property_stack_deco
    def modelAsXml(self):
        self.parent.parametersChanged.emit()

    def _setModelAsXml(self):
        self._model_as_xml = dicttoxml(self._model_as_obj).decode()
        self.modelAsXmlChanged.emit()

    @Property(int, notify=modelChanged)
    def currentItemsIndex(self):
        return self._current_items_index

    @currentItemsIndex.setter
    def currentItemsIndex(self, new_index: int):
        if self._current_items_index == new_index or new_index == -1:
            return
        self._current_items_index = new_index
        self.parent.sampleChanged.emit()

    @Property(int, notify=modelChanged)
    def currentItemsRepetitions(self):
        if self._structure[
                self.currentItemsIndex].type != 'Repeating Multi-layer':
            return 1
        return self._structure[self.currentItemsIndex].repetitions.raw_value

    @currentItemsRepetitions.setter
    def currentItemsRepetitions(self, new_repetitions: int):
        if self._structure[
                self.currentItemsIndex].type != 'Repeating Multi-layer':
            return
        if self._structure[
                self.
                currentItemsIndex].repetitions.raw_value == new_repetitions or new_repetitions == -1:
            return
        self._structure[self.currentItemsIndex].repetitions = new_repetitions
        self.parent.sampleChanged.emit()

    @Property(str, notify=modelChanged)
    def currentItemsType(self):
        return self._structure[self.currentItemsIndex].type

    @currentItemsType.setter
    def currentItemsType(self, type: str):
        if self._structure[self.currentItemsIndex].type == type or type == -1:
            return
        current_layers = self._structure[self.currentItemsIndex].layers
        current_name = self._structure[self.currentItemsIndex].name
        target_position = self.currentItemsIndex
        self._model.remove_item(self.currentItemsIndex)
        if type == 'Multi-layer':
            self._model.add_item(ITEM_LOOKUP[type].from_pars(current_layers,
                                                             current_name))
        elif type == 'Repeating Multi-layer':
            self._model.add_item(ITEM_LOOKUP[type].from_pars(current_layers, 1,
                                                             current_name))
        elif type == 'Surfactant Layer':
            self._model.add_item(ITEM_LOOKUP[type].default())
            self._model.structure[self.currentItemsIndex].conformal_roughness = False
        if target_position != len(self._structure) - 1:
            new_items_list = []
            self._structure[0].layers[0].thickness.enabled = True
            self._structure[0].layers[0].roughness.enabled = True
            self._structure[-1].layers[-1].thickness.enabled = True
            for i, item in enumerate(self._structure):
                if i == target_position:
                    new_items_list.append(
                        self._structure[len(self._structure) - 1])
                elif i == len(self._structure) - 1:
                    new_items_list.append(self._structure[target_position])
                else:
                    new_items_list.append(item)
            while len(self._structure) != 0:
                self._model.remove_item(0)
            for i in range(len(new_items_list)):
                self._model.add_item(new_items_list[i])
            borg.stack.enabled = True
            self._structure[0].layers[0].thickness.enabled = False
            self._structure[0].layers[0].roughness.enabled = False
            self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Property(int, notify=modelChanged)
    def currentLayersIndex(self):
        return self._current_layers_index

    @currentLayersIndex.setter
    def currentLayersIndex(self, new_index: int):
        if self._current_layers_index == new_index or new_index == -1:
            return
        self._current_layers_index = new_index
        self.parent.sampleChanged.emit()

    @Property(bool, notify=modelChanged)
    def constrainApm(self):
        try:
            return self._model.structure[self.currentItemsIndex].constrain_apm
        except AttributeError:
            return

    @constrainApm.setter
    def constrainApm(self, x: bool):
        if self._model.structure[self.currentItemsIndex].constrain_apm == x:
            return 
        self._model.structure[self.currentItemsIndex].constrain_apm = x
        self.parent.sampleChanged.emit()

    @Property(bool, notify=modelChanged)
    def conformalRoughness(self):
        try:
            return self._model.structure[self.currentItemsIndex].conformal_roughness
        except AttributeError:
            return

    @constrainApm.setter
    def conformalRoughness(self, x: bool):
        if self._model.structure[self.currentItemsIndex].conformal_roughness == x:
            return 
        self._model.structure[self.currentItemsIndex].conformal_roughness = x
        if x:
            self._model.structure[self.currentItemsIndex].constrain_solvent_roughness(self._model.structure[self.currentItemsIndex].layers[0].roughness)
        self._model.structure[self.currentItemsIndex].roughness.user_constraints['solvent_roughness'].enabled = x
        self.parent.sampleChanged.emit()

    # # #
    # Actions
    # # #

    def _onModelChanged(self):
        for i in self._structure:
            for j in i.layers:
                j.name = j.material.name + ' Layer'
        self._setModelAsObj()
        self._setModelAsXml()
        self.parent._state_proxy.stateChanged.emit(True)

    def _onCurrentItemsChanged(self):
        self.parent.sampleChanged.emit()

    # # #
    # Slots
    # # #

    # # Items

    @Slot()
    def addNewItems(self):
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        try:
            self._model.add_item(
                MultiLayer.from_pars(
                    Layer.from_pars(self.parent._material_proxy._materials[0], 10.,
                                    1.2),
                    f'Multi-layer {len(self._structure)+1}'))
        except IndexError:
            self.parent._material_proxy.addNewMaterials()
            self._model.add_item(
                MultiLayer.from_pars(
                    Layer.from_pars(self.parent._material_proxy._materials[0], 10.,
                                    1.2),
                    f'Multi-layer {len(self._structure)+1}'))
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot()
    def duplicateSelectedItems(self):
        # This is a fix until deepcopy is worked out
        # Manual duplication instead of creating a copy
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        to_dup = self._structure[self.currentItemsIndex]
        to_dup_layers = []
        for i in to_dup.layers:
            to_dup_layers.append(
                Layer.from_pars(i.material,
                                i.thickness.raw_value,
                                i.roughness.raw_value,
                                name=i.name,
                                interface=self.parent._interface))
        try:
            self._model.add_item(
                RepeatingMultiLayer.from_pars(*to_dup_layers,
                                              to_dup.repetitions.raw_value,
                                              name=to_dup.name))
        except AttributeError:
            self._model.add_item(MultiLayer.from_pars(*to_dup_layers, name=to_dup.name))
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot()
    def moveSelectedItemsUp(self):
        # if borg.stack.enabled:
        #    borg.stack.beginMacro('Loaded default item')
        borg.stack.enabled = False
        # This convoluted approach is necessary as currently the BaseCollection
        # does not allow insertion or popping. In future, this could be
        # replaced with the approach for moving items around
        old_index = self.currentItemsIndex
        new_items_list = []
        if old_index != 0:
            self._structure[0].layers[0].thickness.enabled = True
            self._structure[0].layers[0].roughness.enabled = True
            self._structure[-1].layers[-1].thickness.enabled = True
            for i, item in enumerate(self._structure):
                if i == old_index - 1:
                    new_items_list.append(self._structure[old_index])
                elif i == old_index:
                    new_items_list.append(self._structure[old_index - 1])
                else:
                    new_items_list.append(item)
            while len(self._structure) != 0:
                self._model.remove_item(0)
            for i in range(len(new_items_list)):
                self._model.add_item(new_items_list[i])
            borg.stack.enabled = True
            self._structure[0].layers[0].thickness.enabled = False
            self._structure[0].layers[0].roughness.enabled = False
            self._structure[-1].layers[-1].thickness.enabled = False
            self.parent.sampleChanged.emit()

    @Slot()
    def moveSelectedItemsDown(self):
        # This convoluted approach is necessary as currently the BaseCollection
        # does not allow insertion or popping. In future, this could be
        # replaced with the approach for moving items around
        old_index = self.currentItemsIndex
        new_items_list = []
        if old_index != len(self._structure):
            borg.stack.enabled = False
            self._structure[0].layers[0].thickness.enabled = True
            self._structure[0].layers[0].roughness.enabled = True
            self._structure[-1].layers[-1].thickness.enabled = True
            for i, item in enumerate(self._structure):
                if i == old_index:
                    new_items_list.append(self._structure[old_index + 1])
                elif i == old_index + 1:
                    new_items_list.append(self._structure[old_index])
                else:
                    new_items_list.append(item)
            while len(self._structure) != 0:
                self._model.remove_item(0)
            for i in range(len(new_items_list)):
                self._model.add_item(new_items_list[i])
            borg.stack.enabled = True
            self._structure[0].layers[0].thickness.enabled = False
            self._structure[0].layers[0].roughness.enabled = False
            self._structure[-1].layers[-1].thickness.enabled = False
            self.parent.sampleChanged.emit()

    @Slot(str)
    def removeItems(self, i: str):
        """
        Remove an item from the items list.

        :param i: Index of the item
        :type i: str
        """
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        self._model.remove_item(int(i))
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentItemsName(self, name):
        """
        Sets the name of the currently selected item.

        :param sld: New name
        :type sld: str
        """
        if self._structure[self.currentItemsIndex].name == name:
            return
        self._structure[self.currentItemsIndex].name = name
        self.parent.sampleChanged.emit()

    # # Layers

    @Slot()
    def addNewLayers(self):
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        try:
            self._structure[self.currentItemsIndex].add_layer(
                Layer.from_pars(
                    self.parent._material_proxy._materials[0],
                    10.0,
                    1.2,
                    name=f'Layer {len(self._structure[self.currentItemsIndex].layers)}'
                ))
        except IndexError:
            self.addNewItems()
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot()
    def duplicateSelectedLayers(self):
        # This is a fix until deepcopy is worked out
        # Manual duplication instead of creating a copy
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        to_dup = self._structure[self.currentItemsIndex].layers[
            self.currentLayersIndex]
        self._structure[self.currentItemsIndex].add_layer(
            Layer.from_pars(to_dup.material,
                            to_dup.thickness.raw_value,
                            to_dup.roughness.raw_value,
                            name=to_dup.name))
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot()
    def moveSelectedLayersUp(self):
        old_index = self.currentLayersIndex
        new_layers_list = []
        item = self._structure[self.currentItemsIndex]
        layers = item.layers
        # This convoluted approach is necessary as currently the BaseCollection does
        # not allow insertion or popping. In future, this could be replaced with the
        # approach for moving items around
        if old_index != 0:
            borg.stack.enabled = False
            self._structure[0].layers[0].thickness.enabled = True
            self._structure[0].layers[0].roughness.enabled = True
            self._structure[-1].layers[-1].thickness.enabled = True
            for i, l in enumerate(layers):
                if i == old_index - 1:
                    new_layers_list.append(layers[old_index])
                elif i == old_index:
                    new_layers_list.append(layers[old_index - 1])
                else:
                    new_layers_list.append(l)
            while len(layers) != 0:
                item.remove_layer(0)
            for i in range(len(new_layers_list)):
                item.add_layer(new_layers_list[i])
            borg.stack.enabled = True
            self._structure[0].layers[0].thickness.enabled = False
            self._structure[0].layers[0].roughness.enabled = False
            self._structure[-1].layers[-1].thickness.enabled = False
            self.parent.sampleChanged.emit()

    @Slot()
    def moveSelectedLayersDown(self):
        old_index = self.currentLayersIndex
        new_layers_list = []
        item = self._structure[self.currentItemsIndex]
        layers = item.layers
        # This convoluted approach is necessary as currently the BaseCollection does
        # not allow insertion or popping. In future, this could be replaced with the
        # approach for moving items around
        if old_index != len(layers):
            self._structure[0].layers[0].thickness.enabled = True
            self.structure[0].layers[0].roughness.enabled = True
            self._structure[-1].layers[-1].thickness.enabled = True
            borg.stack.enabled = False
            for i, l in enumerate(layers):
                if i == old_index:
                    new_layers_list.append(layers[old_index + 1])
                elif i == old_index + 1:
                    new_layers_list.append(layers[old_index])
                else:
                    new_layers_list.append(l)
            while len(layers) != 0:
                item.remove_layer(0)
            for i in range(len(new_layers_list)):
                item.add_layer(new_layers_list[i])
            borg.stack.enabled = True
            self._structure[0].layers[0].thickness.enabled = False
            self._structure[0].layers[0].roughness.enabled = False
            self._structure[-1].layers[-1].thickness.enabled = False
            self.parent.sampleChanged.emit()

    @Slot(str)
    def removeLayers(self, i: str):
        """
        Remove a layer from the layers list.

        :param i: Index of the layer
        :type i: str
        """
        self._structure[0].layers[0].thickness.enabled = True
        self._structure[0].layers[0].roughness.enabled = True
        self._structure[-1].layers[-1].thickness.enabled = True
        self._structure[self.currentItemsIndex].remove_layer(int(i))
        self._structure[0].layers[0].thickness.enabled = False
        self._structure[0].layers[0].roughness.enabled = False
        self._structure[-1].layers[-1].thickness.enabled = False
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentLayersMaterial(self, current_index):
        """
        Sets the material of the currently selected layer.

        :param current_index: Material index
        :type sld: str
        """
        material = self.parent._material_proxy._materials[int(current_index)]
        if self._structure[self.currentItemsIndex].layers[
                self.currentLayersIndex].material == material:
            return
        self._structure[self.currentItemsIndex].layers[
            self.currentLayersIndex].assign_material(material)
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentLayersThickness(self, thickness):
        """
        Sets the thickness of the currently selected layer.

        :param sld: New thickness value
        :type sld: float
        """
        print(self._structure)
        if self._structure[self.currentItemsIndex].layers[
                self.currentLayersIndex].thickness == thickness:
            return
        self._structure[self.currentItemsIndex].layers[
            self.currentLayersIndex].thickness = thickness
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentLayersRoughness(self, roughness):
        """
        Sets the roughness of the currently selected layer.

        :param sld: New roughness value
        :type sld: float
        """
        if self._structure[self.currentItemsIndex].layers[
                self.currentLayersIndex].roughness == roughness:
            return
        self._structure[self.currentItemsIndex].layers[
            self.currentLayersIndex].roughness = roughness
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentItemApm(self, apm):
        if self._structure[self.currentItemsIndex].constrain_apm:
            if self._structure[self.currentItemsIndex].area_per_molecule == apm:
                return 
            self._structure[self.currentItemsIndex].area_per_molecule = apm
            self.parent.sampleChanged.emit()
        else:
            if self._structure[self.currentItemsIndex].layers[self.currentLayersIndex].area_per_molecule == apm:
                return 
            self._structure[self.currentItemsIndex].layers[self.currentLayersIndex].area_per_molecule = apm
            self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentLayersSolvation(self, solvation):
        """
        Sets the solvation of the currently selected layer.

        :param solvation: New solvation value
        """
        if self._structure[self.currentItemsIndex].layers[self.currentLayersIndex].solvation == solvation:
            return
        self._structure[self.currentItemsIndex].layers[self.currentLayersIndex].solvation = solvation
        self.parent.sampleChanged.emit()

    @Slot(str)
    def setCurrentLayersSolvent(self, current_index):
        """
        Sets the solvent for the currently selected layer.
        
        :param current_index: Material index. 
        """
        material = self.parent._material_proxy._materials[int(current_index)]
        if self._structure[self.currentItemsIndex].layers[
                self.currentLayersIndex].solvent == material:
            return
        self._structure[self.currentItemsIndex].layers[
            self.currentLayersIndex].assign_material(material)
        self.parent.sampleChanged.emit()

    # # # 
    # Calculations 
    # # #

    def getPureModelReflectometry(self, x):
        structure_dict = self._model.structure.as_dict()
        # print(self._model.structure.as_dict()) 
        pure = Model.from_pars(Structure.from_dict(structure_dict), 1, 0, 0, interface=InterfaceFactory())
        return pure.interface.fit_func(x)