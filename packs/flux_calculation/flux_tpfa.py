import numpy as np
import scipy.sparse as sp

class TpfaFlux:

    def get_gravity_source_term(self):

        centroids = self.data_impress['centroid_volumes']
        source_term_volumes = np.zeros(len(centroids))
        transmissibility_faces = self.data_impress[self.data_impress.variables_impress['transmissibility']]
        source_term_faces = np.zeros(len(transmissibility_faces))
        internal_faces = self.elements_lv0['internal_faces']
        areas_internal_faces = self.data_impress['area'][internal_faces]
        k_harm_internal_faces = self.data_impress['k_harm'][internal_faces]
        dh_internal_faces = self.data_impress['dist_cent'][internal_faces]

        # upwind_grav = np.full((len(internal_faces), 2), False, dtype=bool)

        # import pdb; pdb.set_trace()

        if self.gravity:

            up_g = np.zeros(len(internal_faces), dtype=int)

            gamma = self.data_impress['gama']
            gama_faces = self.data_impress['gama_faces']

            vols_viz_internal_faces = self.elements_lv0['neig_internal_faces']
            v0 = vols_viz_internal_faces
            transmissibility_internal_faces = transmissibility_faces[internal_faces]
            t0 = transmissibility_internal_faces
            zs = centroids[:, 2]
            up_g[zs[v0[:, 1]] >= zs[v0[:, 0]]] = v0[zs[v0[:, 1]] >= zs[v0[:, 0]], 0]
            up_g[zs[v0[:, 1]] < zs[v0[:, 0]]] = v0[zs[v0[:, 1]] < zs[v0[:, 0]], 1]
            lambda_w_internal_faces = self.data_impress['lambda_w'][up_g]
            lambda_o_internal_faces = self.data_impress['lambda_o'][up_g]
            gama_w = self.biphasic_data['gama_w']
            gama_o = self.biphasic_data['gama_o']

            # source_term_internal_faces = -1*(zs[v0[:, 1]]*gamma[v0[:, 1]] - zs[v0[:, 0]]*gamma[v0[:, 0]])*t0
            # source_term_internal_faces = -1*(zs[v0[:, 1]] - zs[v0[:, 0]])*t0*gama_faces[internal_faces]
            source_term_internal_faces = -1*(zs[v0[:, 1]] - zs[v0[:, 0]])*(lambda_w_internal_faces*gama_w + lambda_o_internal_faces*gama_o)*areas_internal_faces*k_harm_internal_faces/dh_internal_faces
            source_term_faces[internal_faces] = source_term_internal_faces

            lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
            cols = np.zeros(len(lines), dtype=np.int32)
            data = np.array([source_term_internal_faces, -source_term_internal_faces]).flatten()
            source_term_volumes = sp.csc_matrix((data, (lines, cols)), shape=(self.n_volumes, 1)).toarray().flatten()

        self.data_impress[self.data_impress.variables_impress['flux_grav_volumes']] = source_term_volumes.copy()
        self.data_impress[self.data_impress.variables_impress['flux_grav_faces']] = source_term_faces.copy()

    def get_flux_faces_and_volumes(self) -> None:

        vols_viz_internal_faces = self.elements_lv0['neig_internal_faces']
        v0 = vols_viz_internal_faces
        internal_faces = self.elements_lv0['internal_faces']
        transmissibility_faces = self.data_impress['transmissibility']
        transmissibility_internal_faces = transmissibility_faces[internal_faces]
        t0 = transmissibility_internal_faces
        area_faces = self.data_impress['area']
        area_internal_faces = area_faces[internal_faces]
        a0 = area_internal_faces
        velocity_faces = np.zeros(self.data_impress['velocity_faces'].shape)
        u_normal = self.data_impress['u_normal']

        x = self.data_impress['pressure']

        ps0 = x[v0[:, 0]]
        ps1 = x[v0[:, 1]]

        # flux_internal_faces = -((ps1 - ps0) * t0 - self.data_impress['flux_grav_faces'][internal_faces])
        flux_internal_faces = -((ps1 - ps0) * t0)
        velocity = (flux_internal_faces / a0).reshape([len(internal_faces), 1])
        velocity = velocity * u_normal[internal_faces]
        velocity_faces[internal_faces] = velocity
        flux_faces = np.zeros(len(self.data_impress['flux_faces']))

        flux_faces[internal_faces] = flux_internal_faces

        lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
        cols = np.repeat(0, len(lines))
        data = np.array([flux_internal_faces, -flux_internal_faces]).flatten()
        flux_volumes = sp.csc_matrix((data, (lines, cols)), shape=(self.n_volumes, 1)).toarray().flatten()

        self.data_impress['flux_volumes'] = flux_volumes
        self.data_impress['flux_faces'] = flux_faces
        self.data_impress['velocity_faces'] = velocity_faces

class TpfaFlux2:

    def get_flux_volumes_and_velocity(self) -> None:

        vols_viz_internal_faces = self.elements_lv0['neig_internal_faces']
        v0 = vols_viz_internal_faces
        n_volumes = len(self.elements_lv0['volumes'])
        internal_faces = self.elements_lv0['internal_faces']
        area_faces = self.data_impress['area']
        area_internal_faces = area_faces[internal_faces]
        a0 = area_internal_faces
        velocity_faces = np.zeros(self.data_impress['velocity_faces'].shape)
        u_normal = self.data_impress['u_normal']
        flux_faces = self.data_impress['flux_faces']

        flux_internal_faces = flux_faces[internal_faces]
        velocity = (flux_internal_faces / a0).reshape([len(internal_faces), 1])
        velocity = velocity * u_normal[internal_faces]
        velocity_faces[internal_faces] = velocity

        lines = np.array([v0[:, 0], v0[:, 1]]).flatten()
        cols = np.repeat(0, len(lines))
        data = np.array([flux_internal_faces, -flux_internal_faces]).flatten()
        flux_volumes = sp.csc_matrix((data, (lines, cols)), shape=(n_volumes, 1)).toarray().flatten()

        self.data_impress['flux_volumes'] = flux_volumes
        self.data_impress['velocity_faces'] = velocity_faces

def get_flux_faces(p0: 'left side pressure',
    p1: 'right side pressure',
    t0: 'transmissibility faces',
    flux_grav_faces: 'gravity flux of faces'
):

    return -((p1 - p0) * t0 - flux_grav_faces)
