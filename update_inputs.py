from packs.utils.info_manager import InfoManager
import os

dd = InfoManager('input_cards/inputs0_2.yml', 'input_cards/inputs0.yml')
dd.save_obj()

if dd['deletar_results']:

    results = 'results'
    ff = os.listdir(results)

    for f in ff:
        if f[-4:] == '.vtk':
            os.remove(os.path.join(results, f))
