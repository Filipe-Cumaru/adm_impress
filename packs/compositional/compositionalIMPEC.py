from ..directories import data_loaded
from ..data_class.data_manager import DataManager
from packs.compositional.properties_calculation import PropertiesCalc
from ..utils import relative_permeability2, phase_viscosity, capillary_pressure
from .partial_derivatives import PartialDerivatives
from ..solvers.solvers_scipy.solver_sp import SolverSp
from .. import directories as direc
import scipy.sparse as sp
from .update_time import delta_time
import numpy as np


class CompositionalFVM:
    def __init__(self, M, data_impress, wells, fprop, fprop_block, kprop, delta_t, load):
        self.n_volumes = data_impress.len_entities['volumes']
        self.all_wells = wells['all_wells'].astype(int)
        self.porosity = data_impress['poro']
        self.cf = np.array(data_loaded['compositional_data']['rock_compressibility']).astype(float)
        self.v0 = M.faces.bridge_adjacencies(M.faces.internal,2,3)
        self.n_internal_faces = len(M.faces.internal)
        self.delta_t = self.runIMPEC(M, data_loaded, data_impress, wells, fprop, fprop_block, kprop, delta_t)

    def runIMPEC(self, M, data_loaded, data_impress, wells, fprop, fprop_block, kprop, delta_t):
        self.update_mobilities(fprop)
        self.dVt_derivatives(fprop, fprop_block, kprop)
        self.update_capillary_pressure(data_loaded, data_impress, fprop, kprop)
        self.get_faces_properties_upwind(fprop, kprop)

        r = 1/2# enter the while loop
        while (r!=1.):
            T = self.update_transmissibility( M, wells, fprop, kprop, delta_t)
            D = self.update_independent_terms(fprop, kprop, wells, delta_t)
            self.update_pressure(T, D, data_impress, fprop)
            self.update_flux_internal_faces(fprop, kprop)
            self.update_flux_volumes(fprop, kprop)
            # For the composition calculation the time step may be different because it treats
            #composition explicitly and this explicit models are conditionally stable - wich can
            #be based on the CFL parameter.
            delta_tcfl = delta_time.update_CFL(delta_t, fprop)
            r = delta_tcfl/delta_t
            delta_t = delta_tcfl

        self.update_composition(fprop, kprop, wells, delta_t)
        return delta_t

    def update_mobilities(self, fprop):
        self.mobilities = fprop.relative_permeabilities / fprop.phase_viscosities

    def dVt_derivatives(self, fprop, fprop_block, kprop):

        self.dVtk = np.zeros([kprop.n_components, self.n_volumes])
        if kprop.load_k:
            self.dVtk[0:kprop.Nc,:], dVtP = PartialDerivatives().dVt_derivatives(fprop, fprop_block, kprop)
        else: dVtP = np.zeros(self.n_volumes)
        if kprop.load_w:
            self.dVtk[kprop.n_components-1,:] = 1 / fprop.ksi_W
            kprop.Cw = np.array(data_loaded['compositional_data']['water_data']['Cw']).astype(float)
            dVwP = fprop.component_mole_numbers[kprop.Nc,:] * fprop.ksi_W0 * kprop.Cw / fprop.ksi_W**2
        else: dVwP = np.zeros(self.n_volumes)

        self.dVtP = dVtP + dVwP

    def get_mobilities_upwind(self, fprop, kprop):
        ''' Using one-point upwind approximation '''
        P_Pcap = fprop.P + self.Pcap
        Pj = P_Pcap[:,self.v0[:,0]]
        Pj_up = P_Pcap[:,self.v0[:,1]]

        self.mobilities_internal_faces = np.zeros([1, kprop.n_phases, self.n_internal_faces])
        mobilities_vols = self.mobilities[:,:,self.v0[:,0]]
        mobilities_vols_up = self.mobilities[:,:,self.v0[:,1]]
        self.mobilities_internal_faces[0,Pj_up <= Pj] = mobilities_vols[0,Pj_up <= Pj]
        self.mobilities_internal_faces[0,Pj_up > Pj] = mobilities_vols_up[0,Pj_up > Pj]

    def get_faces_properties_upwind(self, fprop, kprop):
        self.get_mobilities_upwind(fprop, kprop)
        P_Pcap = fprop.P + self.Pcap
        Pj = P_Pcap[:,self.v0[:,0]]
        Pj_up = P_Pcap[:,self.v0[:,1]]

        self.phase_molar_densities_internal_faces = np.zeros([1, kprop.n_phases, self.n_internal_faces])
        phase_molar_densities_vols = fprop.phase_molar_densities[:,:,self.v0[:,0]]
        phase_molar_densities_vols_up = fprop.phase_molar_densities[:,:,self.v0[:,1]]
        self.phase_molar_densities_internal_faces[0,Pj_up <= Pj] = phase_molar_densities_vols[0,Pj_up <= Pj]
        self.phase_molar_densities_internal_faces[0,Pj_up > Pj] = phase_molar_densities_vols_up[0,Pj_up > Pj]

        self.component_molar_fractions_internal_faces = np.zeros([kprop.n_components, kprop.n_phases, self.n_internal_faces])
        component_molar_fractions_vols = fprop.component_molar_fractions[:,:,self.v0[:,0]]
        component_molar_fractions_vols_up = fprop.component_molar_fractions[:,:,self.v0[:,1]]
        self.component_molar_fractions_internal_faces[:,Pj_up <= Pj] = component_molar_fractions_vols[:,Pj_up <= Pj]
        self.component_molar_fractions_internal_faces[:,Pj_up > Pj] = component_molar_fractions_vols_up[:,Pj_up > Pj]

        self.t0_internal_faces_prod = self.component_molar_fractions_internal_faces * self.phase_molar_densities_internal_faces \
                                * self.mobilities_internal_faces


        #self.pretransmissibility_internal_faces
        # return t0_internal_faces_prod

    def update_transmissibility(self, M, wells, fprop, kprop, delta_t):
        pretransmissibility_faces = M.data[M.data.variables_impress['pretransmissibility']]
        self.pretransmissibility_internal_faces = pretransmissibility_faces[M.faces.internal]

        ''' Transmissibility '''
        t0 = (self.t0_internal_faces_prod).sum(axis = 1)
        t0 = t0 * self.pretransmissibility_internal_faces
        T = np.zeros([self.n_volumes, self.n_volumes, kprop.n_components])

        # Look for a way of doing this not using a loop
        for i in range(kprop.n_components):
            lines = np.array([self.v0[:, 0], self.v0[:, 1], self.v0[:, 0], self.v0[:, 1]]).flatten()
            cols = np.array([self.v0[:, 1], self.v0[:, 0], self.v0[:, 0], self.v0[:, 1]]).flatten()
            data = np.array([-t0[i,:], -t0[i,:], +t0[i,:], +t0[i,:]]).flatten()

            Ta = sp.csc_matrix((data, (lines, cols)), shape = (self.n_volumes, self.n_volumes))
            T[:,:,i] = Ta.toarray()

        T = (T * self.dVtk.T[:,np.newaxis, :]).sum(axis = 2)
        T = T * delta_t
        ''' Transmissibility diagonal term '''
        diag = np.diag((fprop.Vbulk * self.porosity * self.cf - self.dVtP))
        T += diag

        self.T_noCC = np.copy(T)

        ''' Includding contour conditions '''
        T[wells['ws_p'],:] = 0
        T[wells['ws_p'], wells['ws_p']] = 1
        return T


    def update_capillary_pressure(self, data_loaded, data_impress, fprop, kprop):
        """ not working yet"""
        #get_capillary_pressure = getattr(capillary_pressure, data_loaded['compositional_data']['capillary_pressure'])
        #get_capillary_pressure = get_capillary_pressure(data_loaded, data_impress, fprop.phase_molar_densities, fprop.component_molar_fractions)
        #Pcow, Pcog = get_capillary_pressure(data_loaded, fprop.Sw, fprop.So, fprop.Sg)

        self.Pcap = np.zeros([kprop.n_phases,self.n_volumes])
        # Pcap[0,0,:] = Pcog
        # Pcap[0,1,:] = Pcow

    def pressure_independent_term(self, fprop):
        vector = fprop.Vbulk * self.porosity * self.cf - self.dVtP
        pressure_term = vector * fprop.P
        return pressure_term

    def capillary_independent_term(self, fprop, kprop):
        t0_j = self.t0_internal_faces_prod

        # Look for a better way to do this
        cap = np.zeros([kprop.n_components, kprop.n_phases, self.n_volumes])
        for i in range(kprop.n_components):
            for j in range(kprop.n_phases):
                lines = np.array([self.v0[:, 0], self.v0[:, 1], self.v0[:, 0], self.v0[:, 1]]).flatten()
                cols = np.array([self.v0[:, 1], self.v0[:, 0], self.v0[:, 0], self.v0[:, 1]]).flatten()
                data = np.array([t0_j[i,j,:], t0_j[i,j,:], -t0_j[i,j,:], -t0_j[i,j,:]]).flatten()
                T = sp.csc_matrix((data, (lines, cols)), shape = (self.n_volumes, self.n_volumes))
                cap[i,j,:] = T.toarray() @ self.Pcap[j,:]

        cap = cap.sum(axis = 1)
        capillary_term = (cap * self.dVtk).sum(axis = 0)
        # capillary_term = np.sum(self.dVtk * np.sum (fprop.component_molar_fractions *
        #         fprop.phase_molar_densities * self.mobilities * self.Pcap, axis = 1), axis = 0)
        return capillary_term

    def volume_discrepancy_independent_term(self, fprop):
        volume_discrepancy_term = fprop.Vp - fprop.Vt #np.sum(fprop.phase_mole_numbers / fprop.phase_molar_densities, axis = 1).ravel()
        return volume_discrepancy_term

    def well_term(self, kprop, wells):
        self.q = np.zeros([kprop.n_components, self.n_volumes]) #for now
        self.q[:,wells['ws_q']] = wells['values_q'] #for now - its going to change
        well_term = np.sum(self.dVtk * self.q, axis = 0)
        return well_term

    def update_independent_terms(self, fprop, kprop, wells, delta_t):
        self.pressure_term = self.pressure_independent_term(fprop)
        self.capillary_term = self.capillary_independent_term(fprop, kprop)
        self.volume_term = self.volume_discrepancy_independent_term(fprop)
        well_term = self.well_term(kprop, wells)
        independent_terms = self.pressure_term  - self.volume_term  +  delta_t * well_term - delta_t * self.capillary_term
        independent_terms[wells['ws_p']] = wells['values_p']
        return independent_terms

    def update_pressure(self, T, D, data_impress, fprop):
        fprop.P = np.linalg.solve(T,D)
        #p = SolverSp().direct_solver(T, D)
        data_impress['pressure'] = fprop.P

    def update_flux_internal_faces(self, fprop, kprop):
        P_Pcap = fprop.P + self.Pcap #para isso, Pcapj = Pj - P
        Pj = P_Pcap[:,self.v0[:,0]]
        Pj_up = P_Pcap[:,self.v0[:,1]]
        total_flux_internal_faces = - np.sum(self.mobilities_internal_faces * self.pretransmissibility_internal_faces * (Pj_up - Pj) ,axis = 1)
        self.get_mobilities_upwind(fprop, kprop) # a mobilidade aqui é em n + 1
        self.phase_flux_internal_faces = self.mobilities_internal_faces / np.sum(self.mobilities_internal_faces, axis = 1) * total_flux_internal_faces
        # M.flux_faces[M.faces.internal] = total_flux_internal_faces * M.faces.normal[M.faces.internal].T

    def update_flux_volumes(self, fprop, kprop):
        component_flux = np.sum(self.component_molar_fractions_internal_faces * self.phase_molar_densities_internal_faces *
                                self.phase_flux_internal_faces, axis = 1)

        cx = np.arange(kprop.n_components)
        lines = np.array([np.repeat(cx,len(self.v0[:,0])), np.repeat(cx,len(self.v0[:,1]))]).astype(int).flatten()
        cols = np.array([np.tile(self.v0[:,0],kprop.n_components), np.tile(self.v0[:,1], kprop.n_components)]).flatten()
        data = np.array([component_flux, -component_flux]).flatten()
        fprop.component_flux_vols_total = sp.csc_matrix((data, (lines, cols)), shape = (kprop.n_components, self.n_volumes)).toarray()
        # só ta funcionando pra 1d:
        #flux_vols = np.zeros([kprop.n_components,2,self.n_volumes])
        #flux_vols[:,0,self.v0[:,0]] = component_flux
        #flux_vols[:,1,self.v0[:,1]] = -component_flux
        #flux_vols_total = np.sum(flux_vols,axis = 1)

    def update_flux_wells(self, fprop, kprop, wells, delta_t):
        ind_ws_prod = np.argwhere(wells['ws_prod'] == wells['ws_p']).ravel()
        wp = wells['ws_prod'][ind_ws_prod]
        well_term = np.zeros([kprop.n_components,1])
        well_term[0,0] = (self.T_noCC[wp,:] @ fprop.P - self.pressure_term[wp] + self.volume_term[wp] ) / delta_t + self.capillary_term[wp]
        if kprop.n_components > 1:
            mob_k = np.sum(self.mobilities[:,:,wp] * fprop.component_molar_fractions[:,:,wp], axis = 1).ravel()
            C = np.diag(np.ones(kprop.n_components))
            C[1:,0] = -mob_k[1:] / mob_k[0]
            C[0,:] = self.dVtk[:,wp].T
            self.q[:,wp] = np.linalg.solve(C,well_term)
        else: self.q[:,wp] = well_term[0,0] / self.dVtk[:,wp]
        self.q[:,wells['ws_q']] = wells['values_q']
        #wq = wells['ws_q']
        #self.q[:,wells['ws_q']] = ((self.T_noCC[wq,:] @ fprop.P - self.pressure_term[wq] + self.volume_term[wq] ) / delta_t
        #                        + self.capillary_term[wq])/self.dVtk[:,wq]
        #if kprop.load_w and not kprop.load_k: self.q[:,wp] = self.q[:,wells['ws_q']]

    def update_composition(self, fprop, kprop, wells, delta_t):
        if kprop.load_k:
            self.update_flux_wells(fprop, kprop, wells, delta_t)
            fprop.component_mole_numbers = fprop.component_mole_numbers + delta_t * (self.q + fprop.component_flux_vols_total)
        fprop.z = fprop.component_mole_numbers[0:kprop.Nc,:] / np.sum(fprop.component_mole_numbers[0:kprop.Nc,:], axis = 0)
