from .data_manager import DataManager
import numpy as np

class ElementsLv0(DataManager):

    def __init__(self, M, load=False, data_name: str='elementsLv0.npz'):
        super().__init__(data_name, load=load)
        self.mesh = M
        if not load:
            self.run()

        self._loaded = True

    def load_elements_from_mesh(self):

        self._data['volumes'] = self.mesh.volumes.all
        self._data['faces'] = self.mesh.faces.all
        self._data['edges'] = self.mesh.edges.all
        self._data['nodes'] = self.mesh.nodes.all
        self._data['internal_faces'] = self.mesh.faces.internal
        self._data['boundary_faces'] = np.setdiff1d(self._data['faces'], self._data['internal_faces'])
        self._data['neig_faces'] = self.mesh.faces.bridge_adjacencies(self._data['faces'], 2, 3)
        self._data['neig_internal_faces'] = self.mesh.faces.bridge_adjacencies(self._data['internal_faces'], 2, 3)
        self._data['neig_boundary_faces'] = self.mesh.faces.bridge_adjacencies(self._data['boundary_faces'], 2, 3)
        self._data['all_volumes'] = self.mesh.core.all_volumes
        self._data['all_faces'] = self.mesh.core.all_faces
        self._data['all_edges'] = self.mesh.core.all_edges
        self._data['all_nodes'] = self.mesh.core.all_nodes

    def run(self):
        self.load_elements_from_mesh()
