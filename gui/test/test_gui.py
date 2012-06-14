# This file was automatically generated by pywxrc.
# -*- coding: UTF-8 -*-

import wx
import wx.xrc as xrc

__res = None

def get_resources():
    """ This function provides access to the XML resources in this module."""
    global __res
    if __res == None:
        __init_resources()
    return __res




class xrcfpb_frame(wx.Frame):
#!XRCED:begin-block:xrcfpb_frame.PreCreate
    def PreCreate(self, pre):
        """ This function is called during the class's initialization.
        
        Override it for custom setup before the window is created usually to
        set additional window styles using SetWindowStyle() and SetExtraStyle().
        """
        pass
        
#!XRCED:end-block:xrcfpb_frame.PreCreate

    def __init__(self, parent):
        # Two stage creation (see http://wiki.wxpython.org/index.cgi/TwoStageCreation)
        pre = wx.PreFrame()
        self.PreCreate(pre)
        get_resources().LoadOnFrame(pre, parent, "fpb_frame")
        self.PostCreate(pre)

        # Define variables for the controls, bind event handlers
        self.scrwin = xrc.XRCCTRL(self, "scrwin")
        self.fpb = xrc.XRCCTRL(self, "fpb")
        self.panel_1 = xrc.XRCCTRL(self, "panel_1")
        self.panel_2 = xrc.XRCCTRL(self, "panel_2")
        self.panel_3 = xrc.XRCCTRL(self, "panel_3")



class xrcstream_frame(wx.Frame):
#!XRCED:begin-block:xrcstream_frame.PreCreate
    def PreCreate(self, pre):
        """ This function is called during the class's initialization.
        
        Override it for custom setup before the window is created usually to
        set additional window styles using SetWindowStyle() and SetExtraStyle().
        """
        pass
        
#!XRCED:end-block:xrcstream_frame.PreCreate

    def __init__(self, parent):
        # Two stage creation (see http://wiki.wxpython.org/index.cgi/TwoStageCreation)
        pre = wx.PreFrame()
        self.PreCreate(pre)
        get_resources().LoadOnFrame(pre, parent, "stream_frame")
        self.PostCreate(pre)

        # Define variables for the controls, bind event handlers
        self.scrwin = xrc.XRCCTRL(self, "scrwin")
        self.fpb = xrc.XRCCTRL(self, "fpb")
        self.fsp_1 = xrc.XRCCTRL(self, "fsp_1")
        self.fsp_1 = xrc.XRCCTRL(self, "fsp_1")
        self.fsp_1 = xrc.XRCCTRL(self, "fsp_1")
        self.csp_1 = xrc.XRCCTRL(self, "csp_1")
        self.csp_1 = xrc.XRCCTRL(self, "csp_1")
        self.csp_1 = xrc.XRCCTRL(self, "csp_1")





# ------------------------ Resource data ----------------------

def __init_resources():
    global __res
    __res = xrc.EmptyXmlResource()

    wx.FileSystem.AddHandler(wx.MemoryFSHandler())

    test_gui_xrc = '''\
<?xml version="1.0" ?><resource class="">
  <object class="wxFrame" name="fpb_frame">
    <object class="wxBoxSizer">
      <object class="sizeritem">
        <object class="wxScrolledWindow" name="scrwin">
          <object class="wxBoxSizer">
            <orient>wxVERTICAL</orient>
            <object class="sizeritem">
              <object class="odemis.gui.comp.foldpanelbar.FoldPanelBar" name="fpb">
                <object class="odemis.gui.comp.foldpanelbar.FoldPanelItem" name="panel_1">
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <label>Test Panel 1</label>
                  <bg>#1E90FF</bg>
                  <font>
                    <size>13</size>
                    <style>normal</style>
                    <weight>normal</weight>
                    <underlined>0</underlined>
                    <family>default</family>
                    <face>Ubuntu</face>
                    <encoding>UTF-8</encoding>
                  </font>
                  <XRCED>
                    <assign_var>1</assign_var>
                  </XRCED>
                </object>
                <object class="odemis.gui.comp.foldpanelbar.FoldPanelItem" name="panel_2">
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <label>Test Panel 2</label>
                  <collapsed>1</collapsed>
                  <bg>#A9D25E</bg>
                  <XRCED>
                    <assign_var>1</assign_var>
                  </XRCED>
                </object>
                <object class="odemis.gui.comp.foldpanelbar.FoldPanelItem" name="panel_3">
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <object class="wxStaticText">
                    <label>LABEL</label>
                  </object>
                  <label>Test Panel 3</label>
                  <bg>#D08261</bg>
                  <XRCED>
                    <assign_var>1</assign_var>
                  </XRCED>
                </object>
                <spacing>0</spacing>
                <bg>#4D4D4D</bg>
                <XRCED>
                  <assign_var>1</assign_var>
                </XRCED>
              </object>
              <flag>wxEXPAND</flag>
            </object>
          </object>
          <bg>#A52A2A</bg>
          <XRCED>
            <assign_var>1</assign_var>
          </XRCED>
        </object>
        <option>1</option>
        <flag>wxEXPAND</flag>
        <minsize>100,100</minsize>
      </object>
      <orient>wxVERTICAL</orient>
    </object>
    <title>Fold Panel Bar Test Frame</title>
  </object>
  <object class="wxFrame" name="stream_frame">
    <object class="wxBoxSizer">
      <orient>wxVERTICAL</orient>
      <object class="sizeritem">
        <object class="wxScrolledWindow" name="scrwin">
          <object class="wxBoxSizer">
            <orient>wxVERTICAL</orient>
            <object class="sizeritem">
              <object class="odemis.gui.comp.foldpanelbar.FoldPanelBar" name="fpb">
                <object class="odemis.gui.comp.foldpanelbar.FoldPanelItem">
                  <object class="wxPanel" name="test_panel">
                    <object class="wxBoxSizer">
                      <orient>wxVERTICAL</orient>
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.FixedStreamPanel" name="fsp_1">
                          <label>Fixed Stream panel</label>
                          <collapsed>1</collapsed>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                      
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.FixedStreamPanel" name="fsp_1">
                          <label>Fixed Stream panel</label>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.FixedStreamPanel" name="fsp_1">
                          <label>Fixed Stream panel</label>
                          <collapsed>1</collapsed>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.CustomStreamPanel" name="csp_1">
                          <label>Custom Stream panel</label>
                          <collapsed>1</collapsed>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.CustomStreamPanel" name="csp_1">
                          <label>Custom Stream panel</label>
                          <collapsed>1</collapsed>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                      <object class="sizeritem">
                        <object class="odemis.gui.comp.stream.CustomStreamPanel" name="csp_1">
                          <label>Custom Stream panel</label>
                          <collapsed>1</collapsed>
                          <fg>#FFFFFF</fg>
                          <bg>#4D4D4D</bg>
                          <font>
                            <size>9</size>
                            <style>normal</style>
                            <weight>normal</weight>
                            <underlined>0</underlined>
                            <family>default</family>
                            <face>Ubuntu</face>
                            <encoding>UTF-8</encoding>
                          </font>
                          <XRCED>
                            <assign_var>1</assign_var>
                          </XRCED>
                        </object>
                        <flag>wxBOTTOM|wxEXPAND</flag>
                        <border>1</border>
                      </object>
                    </object>
                    <bg>#333333</bg>
                  </object>
                  <label>STREAMS</label>
                  <XRCED>
                    <assign_var>1</assign_var>
                  </XRCED>
                </object>
                <spacing>0</spacing>
                <leftspacing>0</leftspacing>
                <rightspacing>0</rightspacing>
                <bg>#4D4D4D</bg>
                <XRCED>
                  <assign_var>1</assign_var>
                </XRCED>
              </object>
              <flag>wxEXPAND</flag>
            </object>
          </object>
          <bg>#A52A2A</bg>
          <XRCED>
            <assign_var>1</assign_var>
          </XRCED>
        </object>
        <option>1</option>
        <flag>wxEXPAND</flag>
        <minsize>400,400</minsize>
      </object>
    </object>
    <size>400,400</size>
    <title>Stream panel test frame</title>
  </object>
</resource>'''

    wx.MemoryFSHandler.AddFile('XRC/test_gui/test_gui_xrc', test_gui_xrc)
    __res.Load('memory:XRC/test_gui/test_gui_xrc')

