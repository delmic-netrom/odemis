#-*- coding: utf-8 -*-

"""
:author: Rinze de Laat
:copyright: © 2013 Rinze de Laat, Delmic

.. license::

    This file is part of Odemis.

    Odemis is free software: you can redistribute it and/or modify it under the
    terms of the GNU General Public License version 2 as published by the Free
    Software Foundation.

    Odemis is distributed in the hope that it will be useful, but WITHOUT ANY
    WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
    FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
    details.

    You should have received a copy of the GNU General Public License along with
    Odemis. If not, see http://www.gnu.org/licenses/.

"""

#===============================================================================
# Test module for Odemis' gui.comp.overlay module
#===============================================================================

from odemis.gui import model
import logging
import odemis.gui.comp.miccanvas as miccanvas
import odemis.gui.comp.overlay as overlay
import odemis.gui.test as test
import odemis.model as omodel
import unittest
import wx

test.goto_manual()
logging.getLogger().setLevel(logging.DEBUG)

def do_stuff(sequence):
    print "New sequence", sequence

class OverlayTestCase(test.GuiTestCase):

    frame_class = test.test_gui.xrccanvas_frame


    def test_view_select_overlay(self):
        # Create and add a miccanvas
        cnvs = miccanvas.SecomCanvas(self.panel)

        cnvs.SetBackgroundColour(wx.WHITE)
        cnvs.SetForegroundColour("#DDDDDD")
        self.add_control(cnvs, wx.EXPAND, proportion=1, clear=True)

        vsol = overlay.ViewSelectOverlay(cnvs, "test selection")
        cnvs.ViewOverlays.append(vsol)
        cnvs.active_overlay = vsol
        cnvs.current_mode = model.TOOL_ROI

    def test_roa_select_overlay(self):
        # Create and add a miccanvas
        # TODO: Sparc canvas because it's now the only one which supports TOOL_ROA
        # but it should be a simple miccanvas
        cnvs = miccanvas.SparcAcquiCanvas(self.panel)

        self.add_control(cnvs, wx.EXPAND, proportion=1, clear=True)

        rsol = overlay.RepetitionSelectOverlay(cnvs, "Region of acquisition")
        cnvs.WorldOverlays.append(rsol)
        cnvs.active_overlay = rsol
        cnvs.current_mode = model.TOOL_ROA

        gui_loop(SLEEP_TIME)
        wroi = [-0.1, 0.3, 0.2, 0.4] # in m
        rsol.set_physical_sel(wroi)
        gui_loop(SLEEP_TIME)
        wroi_back = rsol.get_physical_sel()
        for o, b in zip(wroi, wroi_back):
            self.assertAlmostEqual(o, b,
                       msg="wroi (%s) != bak (%s)" % (wroi, wroi_back))

        rsol.set_repetition((3, 2))
        rsol.grid_fill()
        gui_loop(SLEEP_TIME)

        rsol.set_repetition((4, 5))
        rsol.point_fill()
        gui_loop(SLEEP_TIME)

    def test_dichotomy_overlay(self):
        cnvs = miccanvas.SecomCanvas(self.panel)
        self.add_control(cnvs, wx.EXPAND, proportion=1, clear=True)

        lva = omodel.ListVA()

        dol = overlay.DichotomyOverlay(cnvs, lva)
        cnvs.ViewOverlays.append(dol)

        dol.sequence_va.subscribe(do_stuff, init=True)
        dol.enable()

        dol.sequence_va.value = [0, 1, 2, 3, 0]

        test.gui_loop(1000)


    def test_spot_mode_overlay(self):
        cnvs = miccanvas.SecomCanvas(self.panel)
        self.add_control(cnvs, wx.EXPAND, proportion=1, clear=True)

        sol = overlay.SpotModeOverlay(cnvs)
        cnvs.ViewOverlays.append(sol)

        test.gui_loop(1000)



if __name__ == "__main__":
    unittest.main()
