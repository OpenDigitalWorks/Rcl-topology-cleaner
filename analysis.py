
# plugin module imports

from sGraph.dual_graph import *
from sGraph.shpFunctions import *
from qgis.core import *
from PyQt4.QtCore import *
import traceback

# SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

class clean(QObject):

    # Setup signals
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, settings, iface):
        QObject.__init__(self)
        self.settings = settings
        self.killed = False
        self.iface = iface

    def run(self):
        ret = None
        if self.settings:
            try:
                # cleaning settings
                layer_name = self.settings['input']
                path = self.settings['output']
                tolerance = self.settings['tolerance']
                base_id = 'id_in'

                # project settings
                n = getLayerByName(layer_name)
                crs = n.dataProvider().crs()
                encoding = n.dataProvider().encoding()
                geom_type = n.dataProvider().geometryType()
                qgsflds = get_field_types(layer_name)

                self.progress.emit(10)

                # shp/postgis to prGraph instance
                transformation_type = 'shp_to_pgr'
                simplify = True
                parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id}
                # error cat: invalids, multiparts
                primal_graph, invalids, multiparts = transformer(parameters).run()
                any_primal_graph = prGraph(primal_graph, base_id, True)

                if self.killed is True: return
                self.progress.emit(20)

                # break at intersections and overlaping geometries
                # error cat: to_break
                broken_primal, to_break = any_primal_graph.break_graph(tolerance, simplify)

                if self.killed is True: return
                self.progress.emit(30)

                # error cat: duplicates
                broken_clean_primal, duplicates_br = broken_primal.rmv_dupl_overlaps()

                if self.killed is True: return
                self.progress.emit(40)

                # transform primal graph to dual graph
                centroids = broken_clean_primal.get_centroids_dict()
                broken_dual = dlGraph(broken_clean_primal.to_dual(True, False, False), broken_clean_primal.uid, centroids, True)

                if self.killed is True: return
                self.progress.emit(50)

                # Merge between intersections
                # error cat: to_merge
                merged_primal, to_merge = broken_dual.merge(broken_clean_primal, tolerance, simplify)

                if self.killed is True: return
                self.progress.emit(60)

                # error cat: duplicates
                merged_clean_primal, duplicates_m = merged_primal.rmv_dupl_overlaps()

                if self.killed is True: return
                self.progress.emit(70)

                name = layer_name + '_cleaned'

                if self.settings['errors']:

                    print "preparing dual"

                    centroids = merged_clean_primal.get_centroids_dict()
                    merged_dual = dlGraph(merged_clean_primal.to_dual(False, False, False), merged_clean_primal.uid, centroids,
                                          True)

                    print "dual ok"
                    if self.killed is True:
                        print "killed"
                        return
                    self.progress.emit(80)

                    print "before islands, orphans"

                    # error cat: islands, orphans
                    islands, orphans = merged_dual.find_islands_orphans(merged_clean_primal)

                    print "identified islands, orphans"

                    if self.killed is True:
                        print "killed"
                        return
                    self.progress.emit(90)

                    # combine all errors
                    error_list = [['invalids', invalids], ['multiparts', multiparts], ['intersections/overlaps', to_break],
                                  ['duplicates', duplicates_br], ['chains', to_merge],
                                  ['islands', islands], ['orphans', orphans]]
                    e_path = None
                    print "before shp"
                    errors = errors_to_shp(error_list, e_path, 'errors', crs, encoding, geom_type)
                    print "after shp"
                else:
                    errors = None

                if self.killed is False:
                    print "survived!"
                    self.progress.emit(100)
                    # return cleaned shapefile and errors
                    cleaned = merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)
                    ret = (errors, cleaned,)

            except Exception, e:
                # forward the exception upstream
                self.error.emit(e, traceback.format_exc())

            self.finished.emit(ret)

    def kill(self):
        self.killed = True


# source: http://stackoverflow.com/questions/20324804/how-to-use-qthread-correctly-in-pyqt-with-movetothread

# Putting *args and/ or **kwargs as the last items in your function definition's argument list
# allows that function to accept an arbitrary number of arguments and/or keyword arguments.


class GenericWorker(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, function, *args, **kwargs):
        super(GenericWorker, self).__init__()

        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.killed = False
        self.start.connect(self.run)

    start = pyqtSignal(str)

    #@pyqtSlot
    def run(self, some_string_arg):
        ret = None
        try:
            ret = self.function(*self.args, **self.kwargs)
            # self.progress.emit()
        except Exception, e:
            self.error.emit(e, traceback.format_exc())

        self.finished.emit(ret)


    def kill(self):
        self.killed = True

#class PeriodicWorker(GenericWorker,transformer):
#    def __init__(self):
#        super(PeriodicWorker,self).__init__()

