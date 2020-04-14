import numpy as np
from packs.directories import data_loaded
from packs import directories as direc
from packs.running.compositional_initial_mesh_properties import initial_mesh
from packs.compositional.compositionalIMPEC import CompositionalFVM
from packs.compositional.stability_check import StabilityCheck
from packs.compositional.properties_calculation import PropertiesCalc
from packs.compositional.update_time import delta_time
from update_inputs_compositional import ComponentProperties, FluidProperties
import update_inputs_compositional
import os
import time

def initialize(load, convert):
    M, elements_lv0, data_impress, wells = initial_mesh(load=load, convert=convert)
    n_volumes = data_impress.len_entities['volumes']
    fprop, fprop_block, kprop = get_initial_properties(M, data_impress, wells, load, data_loaded, n_volumes)
    return M, data_impress, wells, fprop, fprop_block, kprop, load, n_volumes

def get_initial_properties(M, data_impress, wells, load, data_loaded, n_volumes):
    kprop = ComponentProperties(data_loaded)
    P, T = update_inputs_compositional.inputs_overall_properties(data_loaded)
    fprop = FluidProperties(kprop)
    fprop_block = StabilityCheck(P, T, kprop)
    if kprop.load_k:
        fprop_block.run(fprop.z, kprop)
        fprop.run_inputs_k(fprop_block, kprop, n_volumes)
    else: fprop.x = []; fprop.y = []
    if kprop.load_w: fprop.run_inputs_w(T, P, data_loaded, n_volumes)

    prop = PropertiesCalc(n_volumes)
    prop.run_outside_loop(data_impress, wells, fprop, kprop)
    fprop.inputs_missing_properties(kprop)
    return fprop, fprop_block, kprop

class run_simulation:

    def __init__(self, delta_t_initial, data_impress, fprop):
        self.name_current_compositional_results = 'flying/results_caso_m2.npy'
        self.name_all_compositional_results = os.path.join(direc.flying, 'all_compositional_m2_results_')
        self.loop = 0
        self.vpi = 0.0
        self.t = 0.0
        self.contador_vtk = 0
        self.max_contador_vtk = len(data_loaded['compositional_data']['vpis_para_gravar_vtk'])
        fprop.Vbulk = data_impress['volume']
        self.delta_t = delta_t_initial
        self.mesh_name =  'compositional_'
        self.all_compositional_results = self.get_empty_current_compositional_results()

    def run(self, M, data_impress, wells, fprop, fprop_block, kprop, load, n_volumes):
        
        t0 = time.time()
        t_obj = delta_time(fprop) #get wanted properties in t=n

        self.t += self.delta_t

        FVM = CompositionalFVM(M, data_impress, wells, fprop, fprop_block, kprop, self.delta_t, load)

        self.delta_t = FVM.delta_t # if the CFL condition is broken, delta_t is changed
        prop = PropertiesCalc(n_volumes)
        prop.run_inside_loop(data_impress, wells, fprop, kprop)

        if kprop.load_k:
            for i in range(1, n_volumes):
                P = fprop.P[i]
                z = fprop.z[0:kprop.Nc,i] #água não entra
                fprop_block = StabilityCheck(P, fprop.T, kprop)
                fprop_block.run(z, kprop)
                fprop.update_all_volumes(fprop_block, i)

        self.delta_t = t_obj.update_delta_t(self.delta_t, fprop)#get delta_t with properties in t=n and t=n+1
        self.update_loop()
        t1 = time.time()
        dt = t1 - t0
        self.update_current_compositional_results(wells, fprop, dt) #ver quem vou salvar

    def update_loop(self):
        self.loop += 1

    def update_vpi(self):
        #mudar tudinho
        flux_total_inj = np.absolute(self.data_impress['flux_volumes'][self.wells['ws_inj']])
        self.vpi += (flux_total_inj.sum()*self.delta_t)/self.Vp

    def get_empty_current_compositional_results(self):

        return [np.array(['loop', 'delta_t [s]', 'simulation_time [s]', 't [s]', 'pressure [Pa]', 'flux_vols'])]

    def update_current_compositional_results(self, wells, fprop, simulation_time: float = 0.0):

         self.current_compositional_results = np.array([self.loop, self.delta_t, simulation_time, self.t, fprop.P, fprop.component_flux_vols_total])

         self.all_compositional_results.append(self.current_compositional_results)

    def export_current_compositional_results(self):
         np.save(self.name_current_compositional_results, self.current_compositional_results)

    def export_all_compositional_results(self):
         np.save(self.name_all_compositional_results + str(self.loop) + '.npy', np.array(self.all_compositional_results))
         self.all_compositional_results = self.get_empty_current_compositional_results()

    def save_infos(self, data_impress, M):
         self.export_current_compositional_results()
         self.export_all_compositional_results()
         data_impress.update_variables_to_mesh()
         data_impress.export_all_datas_to_npz()
         M.core.print(file=self.mesh_name, extension='.h5m', config_input="input_cards/print_settings.yml")
         # M.core.print(file=self.mesh_name, extension='.vtk', config_input="input_cards/print_settings.yml")
