# coding: utf-8
import argparse
import codecs
import os
import struct

import pygame
from pygame import Color, Rect, Surface, freetype, image

from rectpack.packer import SORT_NONE, PackingBin, newPacker

freetype.init()

ICONS = {
    u'！':'L',
    u'\uff00':'R',
    u'＂':'A',
    u'＃':'B',
    u'）':'X',
    u'（':'Y',
    u'＄':'D_up',
    u'％':'D_down',
    u'＇':'D_left',
    u'＆':'D_right',
    u'＊':'Aim',
}


class Glyph(object):
    char = u''
    x = 0
    y = 0
    __surface = None
    empty = False

    @property
    def surface(self):
        if self.empty:
            return Surface((4, 4), pygame.SRCALPHA, 32)
        if self.__surface:
            return self.__surface
        else:
            return self.font.render(self.char, fgcolor=Color('white'), style=freetype.STYLE_NORMAL)[0]
    
    @surface.setter
    def surface(self, value):
        self.__surface = value
    
    @property
    def rect(self):
        return self.surface.get_rect()

    def __init__(self, char, font, group):
        self.char = char
        self.font = font
        self.group = group
        if char in ICONS:
            self.__surface = image.load('icons/%s.png'%ICONS[char])
            self.xoffset = 0
            self.yoffset = self.rect.height
            self.xadv = self.rect.width
        else:
            metrics = font.get_metrics(char)
            font_rect = font.get_rect(char)
            self.xoffset = font_rect.x
            self.yoffset = font_rect.height - font_rect.y
            self.xadv = int(metrics[0][3])
            if font_rect.width == 0 or font_rect.height == 0:
                self.empty = True

class FontGroup(object):
    def __init__(self, name, font_name, font_size, filter, image_size):
        self.name = name
        self.filter = sorted(filter)
        self.font = freetype.Font(font_name, font_size)
        self.font_size = font_size
        self.glyphs = []
        self.tex_w, self.tex_h = image_size
        self.img_path = 'system/fonts/textures/japfnt.bctex\x00\x00'
    
    @property
    def count(self):
        return len(self.glyphs)
    @property
    def lastchar(self):
        return self.filter[-1]

    def add_chars(self, chars):
        for c in sorted(chars):
            if c > self.lastchar:
                break
            glyph = Glyph(c, self.font, self.name)
            if c not in self.filter:
                glyph.empty = True
            self.glyphs.append(glyph)
    
    def save(self):
        path = '%s.mfnt'%self.name
        fs = open(path, 'wb')

        fs.write('MFNT')
        fs.write(struct.pack('BBBBIIIIIIII', 1, 0, 9, 0, 
        0x28, 
        self.tex_w, self.tex_h, 
        2, 
        self.font_size, self.count, 
        0x28 + len(self.img_path),
        self.count * 0xE + len(self.img_path)))

        fs.write(self.img_path)

        for g in self.glyphs:
            fs.write(struct.pack('hhhhhhh', g.x, g.y, g.rect.width, g.rect.height, g.xoffset, g.rect.height, g.xadv))
        
        fs.seek(align(fs.tell(), 4), 1)

        fs.write('system/fonts/symbols/glyphtablejap.buct\x00')
        data_size = fs.tell() - 0x28

        fs.seek(0x24, 0)
        fs.write(struct.pack('i', data_size))
        
        fs.close()

def align(value, alignment):
    return (-value % alignment + alignment) % alignment

class Font(object):
    chars = []
    glyphs = []
    groups = []

    def __init__(self, image_size=(512, 256)):
        self.tex_w, self.tex_h = image_size

    def add_chars(self, chars):
        for char in chars:
            self.add_char(char)
    
    def add_char(self, char):
        if char == '\n':
            return False
        if char not in self.chars:
            self.chars.append(char)

    def add_group(self, name, font_name, font_size, filter):
        group = FontGroup(name, font_name, font_size, filter, (self.tex_w, self.tex_h))
        self.groups.append(group)

    def remap(self):
        self.chars.sort()
        self.glyphs = []
        for group in self.groups:
            group.add_chars(self.chars)
            self.glyphs.extend(group.glyphs)
        
        
        packer = newPacker(sort_algo=SORT_NONE, rotation=False, bin_algo=PackingBin.Global)
        for glyph in self.glyphs:
            packer.add_rect(glyph.rect.width, glyph.rect.height, rid='%s_%s'%(glyph.group, glyph.char))

        packer.add_bin(self.tex_w, self.tex_h)
        packer.pack()
        rect_list = packer.rect_list()
        for r in rect_list:
            for glyph in self.glyphs:
                if '%s_%s'%(glyph.group, glyph.char) == r[5]:
                    glyph.x = r[1]
                    glyph.y = r[2]
    
    def save(self, texture_path, table_path):
        self.remap()
        self.save_groups()
        self.save_texture(texture_path)
        self.save_table(table_path)
    
    def save_groups(self):
        for group in self.groups:
            group.save()

    def save_texture(self, texture_path):
        surface = Surface((self.tex_w, self.tex_h), pygame.SRCALPHA, 32)
        for g in self.glyphs:
            surface.blit(g.surface, Rect(g.x, g.y, g.rect.width, g.rect.height))
        image.save(surface, texture_path)

    def save_table(self, table_path):
        fs = open(table_path, 'wb')
        fs.write('MUCT')
        fs.write('\x01\x00\x03\x00')
        fs.write(struct.pack('ii', len(self.chars), 0x10))

        for i in range(len(self.chars)):
            fs.write(struct.pack('ii', ord(self.chars[i]), i))

        fs.close()
    
    @property
    def rects(self):
        return [g.rect for g in self.glyphs]

def get_group_attr(gstr, attr_name):
    attr_index = gstr.find(attr_name) + len(attr_name) + 1
    attr_end = gstr.find(':', attr_index)
    result = gstr[attr_index:attr_end] if attr_end >= 0 else gstr[attr_index:]
    if attr_name == 'size':
        return int(result)
    else:
        return result

def main():
    parser = argparse.ArgumentParser(description="Metroid: Samus Returns font generator by LITTOMA, TeamPB, 2018.12")
    parser.add_argument('--width', type=int, required=True, nargs='+', help='Set font texture width.')
    parser.add_argument('--height', type=int, required=True, nargs='+', help='Set font texture height.')
    parser.add_argument('-c', '--charset', required=True, help='Set charset file path. The file must stored in utf-16 encoding.')
    parser.add_argument('-g', '--groups', required=True, nargs='+', help='Set groups. Group string format: "name=GROUP_NAME:font=FONT_NAME:size=FONT_SIZE:filter:FILTER_PATH"')
    parser.add_argument('-t', '--table', required=True, help='Set table file path.')
    parser.add_argument('-x', '--texture', required=True, help='Set texture file path.')
    opts = parser.parse_args()

    font = Font((opts.width, opts.height))
    chars = codecs.open(opts.charset, 'r', 'utf-16').read()
    for group in opts.groups:
        name = get_group_attr(group, 'name')
        font_name = get_group_attr(group, 'font')
        size = get_group_attr(group, 'size')
        filtr = get_group_attr(group, 'filter')
        font.add_group(name, font_name, size, filtr)

    font.add_chars(chars)
    font.save(texture_path=opts.texture, table_path=opts.table)

if __name__ == "__main__":
    main()
