# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadNetworkCleaner
                                 A QGIS plugin
 This plugin cleans the road centre line topology
                              -------------------
        begin                : 2016-10-10
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Spece Syntax Ltd
        email                : I.Kolovou@spacesyntax.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QThread
from PyQt4.QtGui import QAction, QIcon
from qgis.core import QgsMapLayer, QgsMapLayerRegistry, QgsMessageLog
from qgis.gui import QgsMessageBar

from qgis.utils import *

# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from road_network_cleaner_dockwidget import RoadNetworkCleanerDockWidget
import os.path

import analysis

# Import the debug library
# set is_debug to False in release version
is_debug = False
try:
    import pydevd
    has_pydevd = True
except ImportError, e:
    has_pydevd = False
    is_debug = False

class RoadNetworkCleaner:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RoadNetworkCleaner_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&RoadNetworkCleaner')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadNetworkCleaner')
        self.toolbar.setObjectName(u'RoadNetworkCleaner')

        #print "** INITIALIZING RoadNetworkCleaner"

        self.pluginIsActive = False

        # TODO: CHECK IF IT NEEDS TO GET BACK TO self.dockwidget == None
        self.dockwidget = RoadNetworkCleanerDockWidget()
        self.cleaning = None

        # Setup debugger
        if has_pydevd and is_debug:
            pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=True)

        # setup GUI signals
        # self.dockwidget.cleanButton.clicked.connect(self.runCleaning)
        self.dockwidget.cleanButton.clicked.connect(self.startCleaning)
        self.dockwidget.cancelButton.clicked.connect(self.killCleaning)


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('RoadNetworkCleaner', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/RoadNetworkCleaner/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Clean road network'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING RoadNetworkCleaner"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD RoadNetworkCleaner"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&RoadNetworkCleaner'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    def getActiveLayers(self, iface):
        layers_list = []
        for layer in iface.legendInterface().layers():
            if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                if layer.hasGeometryType() and (layer.wkbType() == 2 or layer.wkbType() == 5):
                    layers_list.append(layer.name())
        return layers_list

    def runCleaning(self):
        settings = self.dockwidget.get_settings()
        return analysis.clean(settings).run()

    # SOURCE: Network Segmenter https://github.com/OpenDigitalWorks/NetworkSegmenter

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage(
            "Road network cleaner: ", "%s" % (message),
            level,duration=5)

    def startCleaning(self, settings):
        self.dockwidget.cleaningProgress.reset()
        settings = self.dockwidget.get_settings()
        cleaning = analysis.clean(settings, self.iface)

        # start the cleaning in a new thread
        thread = QThread()
        cleaning.moveToThread(thread)
        cleaning.finished.connect(self.cleaningFinished)
        cleaning.error.connect(self.cleaningError)
        cleaning.warning.connect(self.giveMessage)
        cleaning.progress.connect(self.dockwidget.cleaningProgress.setValue)
        thread.started.connect(cleaning.run)
        thread.start()
        self.thread = thread
        self.cleaning = cleaning

    def cleaningFinished(self, ret):
        # clean up  the worker and thread
        self.cleaning.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.cleaning = None

        if ret:
            # report the result
            # a, b = ret
            for i in ret:
                self.render(i)
            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        else:
            # notify the user that sth went wrong
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

    def cleaningError(self, e, exception_string):
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string
                                    , level=QgsMessageLog.CRITICAL)

    def render(self,vector_layer):
        QgsMapLayerRegistry.instance().addMapLayer(vector_layer)

    def killCleaning(self):
        if self.cleaning:
            # Disconnect signals
            self.cleaning.finished.disconnect(self.cleaningFinished)
            self.cleaning.error.disconnect(self.cleaningError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.progress.disconnect(self.dockwidget.cleaningProgress.setValue)
            # Clean up thread and analysis
            self.cleaning.kill()
            self.cleaning.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.cleaning = None

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING RoadNetworkCleaner"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = RoadNetworkCleanerDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()
            self.dockwidget.popActiveLayers(self.getActiveLayers(self.iface))

