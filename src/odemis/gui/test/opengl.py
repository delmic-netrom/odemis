# -*- coding: utf-8 -*-

"""
Install  PyOpenGL using:

`sudo apt-get  install python-opengl`

or

`pip install PyOpenGL PyOpenGL_accelerate`


"""

import numpy

import wx
import math
import time

from odemis.gui import img
from odemis.gui.test import generate_img_data


try:
    from wx import glcanvas
    haveGLCanvas = True
except ImportError:
    haveGLCanvas = False

try:
    # The Python OpenGL package can be found at
    # http://PyOpenGL.sourceforge.net/
    from OpenGL.GL import *
    from OpenGL.GLUT import *
    import OpenGL.arrays.vbo as glvbo
    haveOpenGL = True
except ImportError:
    haveOpenGL = False

FIT_NONE = 0
FIT_HORZ = 1
FIT_VERT = 2


class Canvas(glcanvas.GLCanvas):

    SQAURE = [(-1, 1), (1, 1), (1, -1), (-1, -1)]

    def __init__(self, parent):
        glcanvas.GLCanvas.__init__(self, parent, -1)
        self.init = False
        self.context = glcanvas.GLContext(self)

        self.fit = FIT_HORZ | FIT_VERT
        self.background = True

        # Metrics for rendering background images pixel perfect
        self._bg_size = None
        self._bg_x_ratio = 1
        self._bg_y_ratio = 1

        self._background_id = None
        self._overlay_id = None
        self._texture_ids = []

        self._img_x_ratio = 1
        self._img_y_ratio = 1

        self.scale = 1.0
        self.scale_step = 2

        self.rot = 0.0
        self.opacity = 1.0

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_PAINT, self.on_paint)

        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mouse_wheel)

    def on_erase_background(self, evt):
        pass  # Do nothing, to avoid flashing on MSW.

    def on_mouse_wheel(self, evt):
        # glMatrixMode(GL_MODELVIEW)

        if evt.ControlDown():
            if evt.GetWheelRotation() > 0:
                self.rot = (self.rot - 5) % 360
            else:
                self.rot = (self.rot + 5) % 360
        elif evt.AltDown():
            if evt.GetWheelRotation() > 0:
                self.opacity = max(0.0, (self.opacity - 0.1))
            else:
                self.opacity = min(1.0, (self.opacity + 0.1))
        else:
            if evt.GetWheelRotation() > 0:
                self.scale /= self.scale_step
            else:
                self.scale *= self.scale_step

        self.Refresh()

    def on_size(self, event):
        wx.CallAfter(self.do_set_viewport)
        event.Skip()

    def add_cairo_draw(self):
        # EmptyBitmap is deprecated in wxPython 3.0.3
        # buff = wx.Bitmap.FromRGBA(*self.ClientSize)
        buff = wx.EmptyBitmapRGBA(self.ClientSize.x, self.ClientSize.y, 100, 0, 50, 150)
        # buff = wx.EmptyBitmap(*self.ClientSize)
        dc = wx.MemoryDC()
        dc.SelectObject(buff)
        #
        # ctx = wxcairo.ContextFromDC(dc)
        #
        # ctx.set_line_width(3)
        # ctx.set_line_join(cairo.LINE_JOIN_MITER)
        # ctx.set_source_rgba(1.0, 0, 0, 1)
        # ctx.move_to(100, 100)
        # ctx.line_to(300, 300)
        # ctx.fill()

        del dc

        # array = numpy.zeros((self.ClientSize.x, self.ClientSize.y, 4), 'uint8')
        # alpha = 100
        # array[:,:,] = (0, 0, 255 * alpha / 255.0, alpha)
        # self.set_image(array)

        im = buff.ConvertToImage()
        # im = img.getImage("logo_delphi.png")
        im.SaveFile('test.png', wx.BITMAP_TYPE_PNG)
        self.set_image(im)

    def on_paint(self, evt):
        self.SetCurrent(self.context)
        if not self.init:
            self.init_gl()
            self.init = True
        self.on_draw()

    def do_set_viewport(self):
        w, h = self.GetClientSize()
        self.SetCurrent(self.context)
        glViewport(0, 0, w, h)

        self._set_projection()

    def _set_projection(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        w, h = self.GetClientSize()

        if self.fit == FIT_HORZ | FIT_VERT:
            glOrtho(-1, 1, 1, -1, -1, 1)
        elif self.fit & FIT_VERT == FIT_VERT:
            aspect_ratio = w / float(h)
            glOrtho(-1 * aspect_ratio, 1 * aspect_ratio, 1, -1, -1, 1)
        elif self.fit & FIT_HORZ == FIT_HORZ:
            aspect_ratio = h / float(w)
            glOrtho(-1, 1, 1 * aspect_ratio, -1 * aspect_ratio, -1, 1)
        elif self.fit & FIT_NONE == FIT_NONE:
            glOrtho(-1, 1, 1, -1, -1, 1)
            # FIXME
            self._img_x_ratio = w / float(1000)
            self._img_y_ratio = h / float(1000)

        if self._bg_size:
            bw, bh = self._bg_size

            self._bg_x_ratio = w / float(bw)
            self._bg_y_ratio = h / float(bh)

    def _add_background(self):
        self._background_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._background_id)

        im = img.getImage("canvasbg.png")
        w, h = self._bg_size = im.GetSize()

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, im.GetData())

        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

    def set_image(self, im):
        self._texture_ids.append(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, self._texture_ids[-1])

        if isinstance(im, wx.Image):
            (w, h) = im.GetSize()

            def split_rgb(seq):
                while seq:
                    yield seq[:3]
                    seq = seq[3:]

            rgb = im.GetData()

            if im.HasAlpha():
                #todo: not tested yet
                alpha = im.GetAlphaBuffer()[:].tobytes()
                rgba = r""
                d = 4

                for i, rgb in enumerate(split_rgb(rgb)):
                    rgba += rgb + alpha[i]

                im = rgba
            else:
                im = rgb
                d = 3

        else:
            w, h, d = im.shape

        if d == 3:
            frmt = GL_RGB
        else:
            frmt = GL_RGBA

        glTexImage2D(GL_TEXTURE_2D, 0, frmt, w, h, 0, frmt, GL_UNSIGNED_BYTE, im)

        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
        glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)

        return len(self._texture_ids) - 1

    def update_image(self, im, idx):

        glBindTexture(GL_TEXTURE_2D, self._texture_ids[idx])
        w, h, d = im.shape
        if d == 3:
            frmt = GL_RGB
        else:
            frmt = GL_RGBA
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, frmt, GL_UNSIGNED_BYTE, im)

    def init_gl(self):
        if self.background:
            self._add_background()
        self._set_projection()

    def on_draw(self):

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # For scaling, put GL_PROJECT and glScale here, at the start

        if self.background:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()

            glMatrixMode(GL_MODELVIEW)

            glLoadIdentity()

            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self._background_id)

            glColor4f(1.0, 1.0, 1.0, 1.0)

            glBegin(GL_QUADS)

            glTexCoord2f(0, 0)
            glVertex2f(-1, -1)

            glTexCoord2f(0, self._bg_y_ratio)
            glVertex2f(-1, 1)

            glTexCoord2f(self._bg_x_ratio, self._bg_y_ratio)
            glVertex2f(1, 1)

            glTexCoord2f(self._bg_x_ratio, 0)
            glVertex2f(1, -1)

            glEnd()

            glDisable(GL_TEXTURE_2D)

            glMatrixMode(GL_PROJECTION)
            glPopMatrix()

        if self._texture_ids:
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_TEXTURE_2D)

            for tids in self._texture_ids:
                glBindTexture(GL_TEXTURE_2D, tids)

                glScalef(self.scale, self.scale, 1)
                glRotate(self.rot, 0, 0, 1)

                glColor4f(1.0, 1.0, 1.0, self.opacity)
                # glColor4f(1.0, 1.0, 1.0, 0.5)

                glBegin(GL_QUADS)

                glTexCoord2f(0, 0)
                glVertex2f(-1, -1)

                glTexCoord2f(0, 1)
                glVertex2f(-1, 1)

                glTexCoord2f(1, 1)
                glVertex2f(1, 1)

                glTexCoord2f(1, 0)
                glVertex2f(1, -1)

                glEnd()

                glLoadIdentity()

            glDisable(GL_TEXTURE_2D)
            glDisable(GL_BLEND)

        self.SwapBuffers()

WIDTH, HEIGHT, DEPTH, ALPHA = 400, 400, 4, 255


class MainWindow(wx.Frame):
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        self.canvas = Canvas(self)
        self.SetSize((500, 400))
        self.Center()
        self.Show()

        self.canvas.set_image(generate_img_data(WIDTH, HEIGHT, depth=DEPTH, alpha=ALPHA))

        self.plas_gen = self.plasma_generator(WIDTH, HEIGHT, 3)
        self.anim_idx = self.canvas.set_image(self.plas_gen.next())
        self.canvas.add_cairo_draw()

        self.draw_timer = wx.PyTimer(self.animate)
        self.draw_timer.Start(33.0)

        self.busy = False
        # self.canvas.set_image(img.getImage("test/test_10x10.png"))

    def animate(self):
        self.canvas.update_image(self.plas_gen.next(), self.anim_idx)
        self.Refresh()
        wx.Yield()

    @staticmethod
    def gen_palette():
        start = time.time()

        palette = numpy.zeros((256, 3), dtype=numpy.uint8)

        r_range = (0, 50, 255, 123)
        g_range = (1, 0, 0, 100)
        b_range = (2, 50, 200, 133)

        palette_conf = [r_range, g_range, b_range]

        for c, start, end, mid in palette_conf:
            palette[..., :-mid, c] = numpy.linspace(start, end, 256 - mid)
            palette[..., -mid:, c] = numpy.linspace(end, start, mid)

        print "Palette done in %f seconds" % (time.time() - start)

        return palette

    @staticmethod
    def gen_plasma(width, height, version):

        start = time.time()

        plasma = numpy.zeros((width, height), dtype=numpy.uint8)

        for x in range(width):
            for y in range(height):
                if version in (1, 3):
                    color = int(
                        128.0 + (128.0 * math.sin(x / 8.0)) +
                        128.0 + (128.0 * math.sin(y / 8.0))
                    ) / 2
                else:
                    color = 0

                if version in (2, 3):
                    color2 = int(
                        128.0 +
                        (128.0 * math.sin(math.sqrt((x - width / 2.0) * (x - width / 2.0) + (y -
                        height / 2.0) * (y - height / 2.0)) / 8.0))
                    )
                else:
                    color2 = 0

                plasma[x, y] = color + color2

        print "Plasma done in %f seconds" % (time.time() - start)

        return plasma

    def plasma_generator(self, width, height, version):

        palette = self.gen_palette()
        plasma = self.gen_plasma(width, height, version)

        buff = numpy.zeros((width, height, 3), dtype=numpy.uint8)

        while True:
            start = time.time()
            palette_shift = int(start * 100)

            buff[...] = palette[(plasma[...] + palette_shift) % 255]

            # print "%f FPS" % (1.0 / (time.time() - start))
            yield buff


if haveGLCanvas and haveOpenGL:
    app = wx.App(False)
    win = MainWindow(None)
    app.MainLoop()

# END THREAD RENDER TEST

#=============================================================================
