# -*- coding: utf-8 -*-
'''
Created on 24 Feb 2016

@author: Éric Piel

Copyright © 2016 Éric Piel, Delmic

This file is part of Odemis.

Odemis is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License version 2 as published by the Free Software Foundation.

Odemis is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with Odemis. If not, see http://www.gnu.org/licenses/.
'''
from __future__ import division

import pkg_resources
import wx


def getStream(fn):
    """
    Opens a resource file as a file
    fn (str): name of the filename (including the extension), starting after
       "src/odemis/gui/img"
    return (file-like object)
    """
    return pkg_resources.resource_stream(__name__, fn)


def getImage(fn):
    """
    Load an image file into a wx.Image
    fn (str): name of the filename (including the extension), starting after
       "src/odemis/gui/img"
    return (wx.Image)
    """
    return wx.Image(getStream(fn))  # , wx.BITMAP_TYPE_PNG)


def getBitmap(fn):
    """
    Load an image file into a wx.Bitmap
    fn (str): name of the filename (including the extension), starting after
       "src/odemis/gui/img"
    return (wx.Bitmap)
    """
    return wx.Bitmap(getImage(fn))


def getIcon(fn):
    """
    Load an image file into a wx.Icon
    fn (str): name of the filename (including the extension), starting after
       "src/odemis/gui/img"
    return (wx.Icon)
    """
    return wx.Icon(getBitmap(fn))
