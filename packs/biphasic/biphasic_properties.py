import numpy as np
import scipy.sparse as sp
from ..data_class.structured_mesh_properties import StructuredMeshProperties


class biphasicProperties(StructuredMeshProperties):

    def gama_volumes_average():
        doc = "The gama_volumes_average property."
        def fget(self):
            gama_w = self.biphasic_data['gama_w']
            gama_o = self.biphasic_data['gama_o']
            lambda_w = self.lambda_w_volumes
            lambda_o = self.lambda_o_volumes
            return np.repeat(gama_w, len(lambda_w))*lambda_w + np.repeat(gama_o, len(lambda_o))*lambda_o
        return locals()
    gama_volumes_average = property(**gama_volumes_average())

    def lambda_w_volumes():
        doc = "The lambda_w_volumes property."
        def fget(self):
            return self.data_impress['krw']/self.biphasic_data['mi_w']
        return locals()
    lambda_w_volumes = property(**lambda_w_volumes())

    def lambda_o_volumes():
        doc = "The lambda_o_volumes property."
        def fget(self):
            return self.data_impress['kro']/self.biphasic_data['mi_o']
        return locals()
    lambda_o_volumes = property(**lambda_o_volumes())

    def lambda_t_volumes():
        doc = "The lambda_t_volumes property."
        def fget(self):
            return self.lambda_w_volumes + self.lambda_o_volumes
        return locals()
    lambda_t_volumes = property(**lambda_t_volumes())

    def fw_volumes():
        doc = "The fw_volumes property."
        def fget(self):
            return self.lambda_w_volumes/self.lambda_t_volumes
        return locals()
    fw_volumes = property(**fw_volumes())

    def lambda_w_internal_faces():
        doc = "The lambda_w_internal_faces property."
        def fget(self):
            # return self.data_impress['lambda_w'][self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            return self.lambda_w_volumes[self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
        return locals()
    lambda_w_internal_faces = property(**lambda_w_internal_faces())

    def lambda_o_internal_faces():
        doc = "The lambda_o_internal_faces property."
        def fget(self):
            # return self.data_impress['lambda_o'][self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            return self.lambda_o_volumes[self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate_o']]]
        return locals()
    lambda_o_internal_faces = property(**lambda_o_internal_faces())

    def lambda_t_internal_faces():
        doc = "The lambda_t_internal_faces property."
        def fget(self):
            # return self.data_impress['lambda_t'][self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            # return self.lambda_t_volumes[self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            return self.lambda_w_internal_faces + self.lambda_o_internal_faces
        return locals()
    lambda_t_internal_faces = property(**lambda_t_internal_faces())

    def fw_internal_faces():
        doc = "The fw_internal_faces property."
        def fget(self):
            # return self.data_impress['fw_vol'][self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            # return self.fw_volumes[self.elements_lv0['neig_internal_faces'][self._data['upwind_identificate']]]
            return self.lambda_w_internal_faces/self.lambda_t_internal_faces
        return locals()
    fw_internal_faces = property(**fw_internal_faces())

    def flux_press_w_internal_faces():
        doc = "The flux_press_w_internal_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            areas_internal_faces = self.data_impress['area'][internal_faces]
            k_harm_internal_faces = self.data_impress['k_harm'][internal_faces]

            flux_press_w_internal_faces = -self.grad_p_internal_faces*areas_internal_faces*k_harm_internal_faces*self.lambda_w_internal_faces

            return flux_press_w_internal_faces
        return locals()
    flux_press_w_internal_faces = property(**flux_press_w_internal_faces())

    def flux_press_o_internal_faces():
        doc = "The flux_press_o_internal_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            areas_internal_faces = self.data_impress['area'][internal_faces]
            k_harm_internal_faces = self.data_impress['k_harm'][internal_faces]

            flux_press_o_internal_faces = -self.grad_p_internal_faces*areas_internal_faces*k_harm_internal_faces*self.lambda_o_internal_faces
            return flux_press_o_internal_faces
        return locals()
    flux_press_o_internal_faces = property(**flux_press_o_internal_faces())

    def flux_grav_w_internal_faces():
        doc = "The flux_grav_w_internal_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            if not self.gravity:
                return np.zeros(len(internal_faces))
            areas_internal_faces = self.data_impress['area'][internal_faces]
            k_harm_internal_faces = self.data_impress['k_harm'][internal_faces]
            up_g = self.up_g
            lambda_w_internal_faces = self.lambda_w_volumes[up_g]
            gama_w = self.biphasic_data['gama_w']

            flux_grav_w_internal_faces = -1*(self.grad_z_internal_faces)*(lambda_w_internal_faces*gama_w)*areas_internal_faces*k_harm_internal_faces
            return flux_grav_w_internal_faces
        return locals()
    flux_grav_w_internal_faces = property(**flux_grav_w_internal_faces())

    def flux_grav_o_internal_faces():
        doc = "The flux_grav_o_internal_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            if not self.gravity:
                return np.zeros(len(internal_faces))
            areas_internal_faces = self.data_impress['area'][internal_faces]
            k_harm_internal_faces = self.data_impress['k_harm'][internal_faces]
            up_g = self.up_g
            lambda_o_internal_faces = self.lambda_o_volumes[up_g]
            gama_o = self.biphasic_data['gama_o']

            flux_grav_o_internal_faces = -1*(self.grad_z_internal_faces)*(lambda_o_internal_faces*gama_o)*areas_internal_faces*k_harm_internal_faces
            return flux_grav_o_internal_faces
        return locals()
    flux_grav_o_internal_faces = property(**flux_grav_o_internal_faces())

    def flux_grav_w_faces():
        doc = "The flux_grav_w_faces property."
        def fget(self):
            flux_grav_w_faces = np.zeros(len(self.elements_lv0['faces']))
            if self.gravity:
                pass
            else:
                return flux_grav_w_faces
            internal_faces = self.elements_lv0['internal_faces']
            flux_grav_w_faces[internal_faces] = self.flux_grav_w_internal_faces
            return flux_grav_w_faces
        return locals()
    flux_grav_w_faces = property(**flux_grav_w_faces())

    def flux_grav_o_faces():
        doc = "The flux_grav_o_faces property."
        def fget(self):
            flux_grav_o_faces = np.zeros(len(self.elements_lv0['faces']))
            if self.gravity:
                pass
            else:
                return flux_grav_o_faces
            internal_faces = self.elements_lv0['internal_faces']
            flux_grav_o_internal_faces = self.flux_grav_o_internal_faces
            flux_grav_o_faces[internal_faces] = flux_grav_o_internal_faces
            return flux_grav_o_faces
        return locals()
    flux_grav_o_faces = property(**flux_grav_o_faces())

    def flux_grav_total_faces():
        doc = "The flux_grav_total_faces property."
        def fget(self):
            return self.flux_grav_w_faces + self.flux_grav_o_faces
        return locals()
    flux_grav_total_faces = property(**flux_grav_total_faces())

    def flux_w_internal_faces():
        doc = "The flux_w_internal_faces property."
        def fget(self):
            return self.flux_press_w_internal_faces + self.flux_grav_w_internal_faces
        return locals()
    flux_w_internal_faces = property(**flux_w_internal_faces())

    def flux_o_internal_faces():
        doc = "The flux_o_internal_faces property."
        def fget(self):
            return self.flux_press_o_internal_faces + self.flux_grav_o_internal_faces
        return locals()
    flux_o_internal_faces = property(**flux_o_internal_faces())

    def flux_internal_faces():
        doc = "The flux_internal_faces property."
        def fget(self):
            return self.flux_w_internal_faces + self.flux_o_internal_faces
        return locals()
    flux_internal_faces = property(**flux_internal_faces())

    def flux_o_faces():
        doc = "The flux_o_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            flux_o_faces = np.zeros(len(self.elements_lv0['faces']))
            flux_o_faces[internal_faces] = self.flux_o_internal_faces
            return flux_o_faces
        return locals()
    flux_o_faces = property(**flux_o_faces())

    def flux_w_faces():
        doc = "The flux_w_faces property."
        def fget(self):
            internal_faces = self.elements_lv0['internal_faces']
            flux_w_faces = np.zeros(len(self.elements_lv0['faces']))
            flux_w_faces[internal_faces] = self.flux_w_internal_faces
            return flux_w_faces
        return locals()
    flux_w_faces = property(**flux_w_faces())

    def flux_faces():
        doc = "The flux_faces property."
        def fget(self):
            return self.flux_w_faces + self.flux_o_faces
        return locals()
    flux_faces = property(**flux_faces())

    def flux_volumes():
        doc = "The flux_volumes property."
        def fget(self):
            flux_internal_faces = self.flux_internal_faces
            v0 = self.elements_lv0['neig_internal_faces']
            n_volumes = len(self.data_impress['GID_0'])
            lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
            cols = np.repeat(0, len(lines))
            data = np.array([flux_internal_faces, -flux_internal_faces]).flatten()
            flux_volumes = sp.csc_matrix((data, (lines, cols)), shape=(self.n_volumes, 1)).toarray().flatten()
            return flux_volumes
        return locals()
    flux_volumes = property(**flux_volumes())

    def flux_w_volumes():
        doc = "The flux_w_volumes property."
        def fget(self):
            v0 = self.elements_lv0['neig_internal_faces']
            n_volumes = len(self.data_impress['GID_0'])
            flux_w_internal_faces = self.flux_w_internal_faces
            lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
            cols = np.repeat(0, len(lines))
            data = np.array([flux_w_internal_faces, -flux_w_internal_faces]).flatten()
            flux_w_volumes = sp.csc_matrix((data, (lines, cols)), shape=(self.n_volumes, 1)).toarray().flatten()
            ws_prod = self.wells['ws_prod']
            ws_inj = self.wells['ws_inj']
            flux_volumes = self.flux_volumes

            if len(ws_prod) > 0:
                flux_w_volumes[ws_prod] -= flux_volumes[ws_prod]*self.fw_volumes[ws_prod]

            if len(ws_inj) > 0:
                flux_w_volumes[ws_inj] -= flux_volumes[ws_inj]*self.fw_volumes[ws_inj]

            return flux_w_volumes
        return locals()
    flux_w_volumes = property(**flux_w_volumes())

    def flux_o_volumes():
        doc = "The flux_o_volumes property."
        def fget(self):
            v0 = self.elements_lv0['neig_internal_faces']
            n_volumes = len(self.data_impress['GID_0'])
            flux_volumes = self.flux_volumes
            flux_o_internal_faces = self.flux_o_internal_faces
            lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
            cols = np.repeat(0, len(lines))
            data = np.array([flux_o_internal_faces, -flux_o_internal_faces]).flatten()
            flux_o_volumes = sp.csc_matrix((data, (lines, cols)), shape=(self.n_volumes, 1)).toarray().flatten()
            ws_prod = self.wells['ws_prod']
            flux_o_volumes[ws_prod] -= flux_volumes[ws_prod]*(1 - self.fw_volumes[ws_prod])
            return flux_o_volumes
        return locals()
    flux_o_volumes = property(**flux_o_volumes())

    def velocity_w_faces():
        doc = "The velocity_w_faces property."
        def fget(self):
            areas = self.data_impress['area']
            return self.flux_w_faces/areas
        return locals()
    velocity_w_faces = property(**velocity_w_faces())

    def velocity_o_faces():
        doc = "The velocity_o_faces property."
        def fget(self):
            areas = self.data_impress['area']
            return self.flux_o_faces/areas
        return locals()
    velocity_o_faces = property(**velocity_o_faces())

    def velocity_faces():
        doc = "The velocity_faces property."
        def fget(self):
            return self.velocity_w_faces + self.velocity_o_faces
        return locals()
    velocity_faces = property(**velocity_faces())

    def velocity_w_faces_vec():
        doc = "The velocity_w_faces_vec property."
        def fget(self):
            u_normal = self.data_impress['u_normal']
            return self.velocity_w_faces.reshape([len(self.elements_lv0['faces']), 1]) * u_normal
        return locals()
    velocity_w_faces_vec = property(**velocity_w_faces_vec())

    def velocity_o_faces_vec():
        doc = "The velocity_o_faces_vec property."
        def fget(self):
            u_normal = self.data_impress['u_normal']
            return self.velocity_o_faces.reshape([len(self.elements_lv0['faces']), 1]) * u_normal
        return locals()
    velocity_o_faces_vec = property(**velocity_o_faces_vec())

    def velocity_faces_vec():
        doc = "The velocity_faces_vec property."
        def fget(self):
            return self.velocity_w_faces_vec + self.velocity_o_faces_vec
        return locals()
    velocity_faces_vec = property(**velocity_faces_vec())

    def flux_w_faces_vec():
        doc = "The flux_w_faces_vec property."
        def fget(self):
            areas = self.data_impress['area'].reshape(len(self.data_impress['area']), 1)
            return self.velocity_w_faces_vec*areas
        return locals()
    flux_w_faces_vec = property(**flux_w_faces_vec())

    def flux_o_faces_vec():
        doc = "The flux_o_faces_vec property."
        def fget(self):
            areas = self.data_impress['area'].reshape(len(self.data_impress['area']), 1)
            return self.velocity_o_faces_vec*areas
        return locals()
    flux_o_faces_vec = property(**flux_o_faces_vec())

    def change_upwind_o(self):
        self._data['upwind_identificate_o'] = ~self._data['upwind_identificate_o']
