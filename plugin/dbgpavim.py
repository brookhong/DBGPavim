# encoding: utf-8
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab
# -*- c--oding: ko_KR.UTF-8 -*-
# remote PHP debugger : remote debugger interface to DBGp protocol
#
# Copyright (c) 2012-2013 Brook Hong
#
# The MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#
# Authors:
#    Brook Hong <hzgmaxwell <at> hotmail.com>
#    The plugin was originally writen by --
#    Seung Woo Shin <segv <at> sayclub.com>
#    I rewrote it with a new debugger engine, please diff this file to find code change.

import os
import sys
import vim
import socket
import base64
import traceback
import xml.etree.ElementTree as ET

import string
import time, subprocess
from threading import Thread,Lock

def getFilePath(s):
  if s[:7] == "file://":
    fn = s[7:]
  else:
    fn = s
  win = 0
  if fn[2] == ':':
    fn = fn[1:]
    win = 1
  return [fn, win]

tracelog = open(os.getenv("HOME").replace("\\","/")+"/.dbgpavim.trace",'w')
def DBGPavimTrace(log):
  tracelog.write("\n"+log+"\n")
  tracelog.flush()

class VimWindow(object):
  """ wrapper class of window of vim """
  def __init__(self, name = 'DEBUG_WINDOW'):
    """ initialize """
    self.name       = name
    self.method     = "new"
    self.buffer     = None
    self.firstwrite = 1
  def isprepared(self):
    """ check window is OK """
    if self.buffer == None or len(dir(self.buffer)) == 0 or self.getwinnr() == -1:
      return 0
    return 1
  def prepare(self):
    """ check window is OK, if not then create """
    if not self.isprepared():
      self.w_create(self.method)
  def before_create(self):
    vim.command("1wincmd w")
  def on_create(self):
    self.w_command('setl noswf')
    pass
  def getwinnr(self):
    return int(vim.eval("bufwinnr('"+self.name+"')"))
  def focus(self):
    winnr = self.getwinnr()
    vim.command(str(winnr) + 'wincmd w')
  def getWidth(self):
    return int(vim.eval("winwidth(bufwinnr('"+self.name+"'))"))
  def getHeight(self):
    return int(vim.eval("winheight(bufwinnr('"+self.name+"'))"))
  def write(self, msg, lineno = 0):
    """ append last """
    self.prepare()
    if self.firstwrite == 1:
      self.firstwrite = 0
      self.buffer[:] = str(msg).split('\n')
    else:
      if lineno == 0:
        self.buffer.append(msg.split('\n'))
        self.w_command('normal G')
      else:
        self.buffer.append(str(msg).split('\n'), lineno)
        self.w_command("normal %dG" % (lineno+1))
    #self.window.cursor = (len(self.buffer), 1)
  def w_create(self, method = 'new'):
    """ create window """
    self.method = method
    self.before_create()
    vim.command('silent ' + method + ' ' + self.name)
    vim.command("setlocal buftype=nofile")
    vim.command("setlocal nolist")
    self.buffer = vim.current.buffer
    self.width  = int( vim.eval("winwidth(0)")  )
    self.height = int( vim.eval("winheight(0)") )
    self.on_create()
  def w_destroy(self):
    """ destroy window """
    if self.buffer == None or len(dir(self.buffer)) == 0:
      return
    self.w_command('bdelete "%s"' % self.name)
    self.firstwrite = 1
  def clean(self):
    """ clean all datas in buffer """
    self.prepare()
    self.buffer[:] = []
    self.firstwrite = 1
  def w_command(self, cmd):
    """ go to my window & execute command """
    self.prepare()
    winnr = self.getwinnr()
    if winnr != int(vim.eval("winnr()")):
      vim.command(str(winnr) + 'wincmd w')
    vim.command(cmd)
  def render(self, xml):
    self.write(ET.tostring(xml))

class StackWindow(VimWindow):
  def __init__(self, name = 'STACK_WINDOW'):
    VimWindow.__init__(self, name)
  def render(self, xml):
    lines = ""
    for node in xml:
      wr = node.get('where')
      if wr == None:
        wr = "{main}"
      if node.tag != '{urn:debugger_protocol_v1}stack':
        return VimWindow.render(self, node)
      else:
        if wr != '{main}':
          fmark = '()'
        else:
          fmark = ''
        [fn, win] = getFilePath(node.get('filename'))
        fn = dbgPavim.localPathOf(fn)
        lines += str('%-2s %-15s %s:%s\n' % (node.get('level'), wr+fmark, fn, node.get('lineno')))
    self.write(lines)
  def on_create(self):
    super(StackWindow, self).on_create()
    vim.command('nnoremap <silent> <buffer> <Enter> :call DbgpavimStackWindowOnEnter()<CR>')
    vim.command('call DbgpavimBindKeys()')
    vim.command('autocmd BufWinLeave <buffer> python dbgPavim.closeCurrentSession()')
    vim.command('highlight CurStack term=reverse ctermfg=White ctermbg=Red gui=reverse')
    self.highlight_stack(0)
  def highlight_stack(self, no):
    self.w_command('syntax clear')
    vim.command('syntax region CurStack start="^' +str(no)+ ' " end="$"')

class WatchWindow(VimWindow):
  def __init__(self, name = 'WATCH_WINDOW'):
    VimWindow.__init__(self, name)
  def decode_string(self, msg, encoding):
    if encoding == 'base64':
      value = base64.decodestring(msg)
    elif encoding == '' or encoding == None or encoding == 'None':
      value = msg
    else:
      value = "(e:%s) %s" % (encoding, msg)
    return value
  def parseNode1(self, p):
    fullname = p.get('fullname')
    if fullname == None:
      fullname = p.get('name')
    val = None
    if p.text != None:
      val = self.decode_string(p.text, p.get('encoding'))
    return (fullname, val)
  def parseNode2(self, p):
    fullname_node = p.find('{urn:debugger_protocol_v1}fullname')
    fullname = self.decode_string(fullname_node.text, fullname_node.get('encoding'))
    value_node = p.find('{urn:debugger_protocol_v1}value')
    val = None
    if value_node != None and value_node.text != None:
      val = self.decode_string(value_node.text, value_node.get('encoding'))
    return (fullname, val)
  def parseProperty(self, p, level, parser, command = None):
    (fullname, val) = parser(p)
    if command == 'eval':
      if self.language == 'php':
        fullname = "$evalResult" if (fullname == None) else ('$evalResult->%s'%(fullname))
      else:
        fullname = "evalResult" if (fullname == None) else ('evalResult->%s'%(fullname))
    else:
      fullname = "" if (fullname == None) else fullname
    tp = p.get('type')
    children = p.get('children')
    properties = p.findall('{urn:debugger_protocol_v1}property')
    size = p.get('size')
    if size == None:
      size = p.get('numchildren')
    size = ('[%s]' % (size)) if size != None else ""
    if val != None:
      value = "(%s%s) '%s'" % (tp, size, val)
    elif tp == "null":
      value = "(null)"
    else:
      if tp == "object":
        tp = tp+"|"+p.get('classname')
      if children == "1" and len(properties) == 0:
        value = "(%s%s)+" % (tp, size)
      else:
        value = "(%s%s)" % (tp, size)
    out = ('%s%s = %s;' % (" "*level, fullname.ljust(32-level), value))
    for pp in properties:
      out += '\n'+self.parseProperty(pp, level+2, parser, command)
    return out
  def render(self, xml, lineno = 0):
    command = xml.get('command')
    level = 0
    out = ""
    if lineno > 0:
      line = self.buffer[lineno-1]
      del self.buffer[lineno-1]
      lineno -= 1
      level = len(line)-len(line.lstrip())
    elif command != None and command != 'eval':
      out += ("\n%sby %s\n" % (self.commenter, xml.get('command')))
    properties = xml.findall('{urn:debugger_protocol_v1}property')
    if properties[0].find('{urn:debugger_protocol_v1}fullname') != None:
      parser = getattr(self, 'parseNode2')
    else:
      parser = getattr(self, 'parseNode1')
    for p in properties:
      out += self.parseProperty(p, level, parser, command)
      if lineno == 0:
        out += "\n"
    self.write(out, lineno)
  def on_create(self):
    super(WatchWindow, self).on_create()
    self.commenter = '// '
    if self.language == 'php':
      self.write('<?')
    elif self.language == 'python':
      self.commenter = '## '
    self.w_command('setl noai nocin')
    vim.command('setl wrap fdm=manual fmr={{{,}}} ft=%s fdl=1' % self.language)
    vim.command('inoremap <buffer> <cr> <esc>:python dbgPavim.session_command("watch_execute")<cr>')
    vim.command('nnoremap <silent> <buffer> <Enter> :call DbgpavimWatchWindowOnEnter()<CR>')
    vim.command('call DbgpavimBindKeys()')
    vim.command('autocmd BufWinLeave <buffer> python dbgPavim.closeCurrentSession()')
  def input(self, mode, arg = ''):
    if arg == '%v%':
      arg = vim.eval('@v')
    self.prepare()
    line = self.buffer[-1]
    if line[:len(mode)+1] == self.commenter+'=> '+mode+':':
      self.buffer[-1] = line + arg
    else:
      self.buffer.append(self.commenter+'=> '+mode+': '+arg)
    self.w_command('normal G')
  def get_command(self):
    line = self.buffer[-1]
    if line[0:11] == self.commenter+'=> exec:':
      print "exec does not supported by xdebug now."
      return ('none', '')
      #return ('exec', line[11:].strip(' '))
    elif line[0:11] == self.commenter+'=> eval:':
      return ('eval', line[11:].strip(' '))
    else:
      return ('none', '')

class HelpWindow(VimWindow):
  def __init__(self, name = 'HELP__WINDOW'):
    VimWindow.__init__(self, name)
  def before_create(self):
    pass
  def on_create(self):
    super(HelpWindow, self).on_create()
    if vim.eval('g:dbgPavimLang') == 'cn' :
      self.write(                                                          \
        '[ Function Keys ]                    | [ Command Mode ]             \n' + \
        '  <F1>   打开帮助窗口                | :Bp [arg] 切换断点[中断条件] \n' + \
        '  <F2>   逐语句调试                  | :Up 切换至上一个文件         \n' + \
        '  <F3>   逐过程调试                  | :Dn 切换至下一个文件         \n' + \
        '  <F4>   运行至断点                  | :Bl 查看所有断点             \n' + \
        '  <F5>   开始调试                    | :Pg 输出当前变量             \n' + \
        '  <F6>   退出调试                    | :Bc 清除所有断点             \n' + \
        '  <F7>   监视变量                    | :Bu 恢复Bc清除的所有断点     \n' + \
        '  <F8>   切换自动调试模式            |                              \n' + \
        '  <F9>   切换监视窗口                |                              \n' + \
        '  <F10>  切换断点                    |                              \n' + \
        '  <F11>  输出所有变量                |                              \n' + \
        '  <F12>  输出当前变量                |                              \n' + \
        '  获取帮助和最新版本,请访问 https://github.com/brookhong/DBGPavim   \n' + \
        '')
    else :
      self.write(                                                          \
        '[ Function Keys ]                    | [ Command Mode ]             \n' + \
        '  <F1>   toggle help window          | :Bp toggle breakpoint        \n' + \
        '  <F2>   step into                   | :Up stack up                 \n' + \
        '  <F3>   step over                   | :Dn stack down               \n' + \
        '  <F4>   step out                    | :Bl list breakpoints         \n' + \
        '  <F5>   run                         | :Pg property get             \n' + \
        '  <F6>   quit debugging              | :Bc disable all breakpoints  \n' + \
        '  <F7>   eval                        | :Bu enabled all breakpoints  \n' + \
        '  <F8>   toggle dbgPavimBreakAtEntry |                              \n' + \
        '  <F9>   toggle layout               |                              \n' + \
        '  <F10>  toggle breakpoint           |                              \n' + \
        '  <F11>  get all context             |                              \n' + \
        '  <F12>  get property at cursor      |                              \n' + \
        '                                                                    \n' + \
        '  For more instructions and latest version,                         \n' + \
        '               pleae refer to https://github.com/brookhong/DBGPavim \n' + \
        '')
    vim.command('call DbgpavimBindKeys()')
    vim.command('1')

class ConsoleWindow(VimWindow):
  def __init__(self, name = 'CONSOLE__WINDOW'):
    VimWindow.__init__(self, name)
  def before_create(self):
    pass
  def on_create(self):
    super(ConsoleWindow, self).on_create()
    vim.command('setlocal autoread')

class DebugUI:
  """ DEBUGUI class """
  def __init__(self, stackwinRatio, watchwinRatio):
    """ initialize object """
    self.stackwinRatio  = stackwinRatio
    self.watchwinRatio  = watchwinRatio
    self.stackwinHeight = 1
    self.watchwinWidth  = 1
    self.helpwin        = None
    self.file           = None
    self.line           = None
    self.cursign        = None
    self.cliwin         = None
    self.backup_ssop    = vim.eval('&ssop')

  def u_create(self, session):
    """ change mode to debug """
    self.session = session
    self.watchwin       = WatchWindow(session.address+"-WATCH_WINDOW")
    self.stackwin       = StackWindow(session.address+"-STACK_WINDOW")
    self.watchwin.language = session.language

    vim.command('tabnew')                # create srcview window (winnr=1)
    vim.command('setl nolist')
    vim.command('let t:dbgpavimDebugging="%s"' % session.address)

    """ create windows """
    self.totalW = int(vim.eval('winwidth(0)'))
    self.totalH = int(vim.eval('winheight(0)'))
    self.stackwinHeight = int(self.totalH*self.stackwinRatio)
    self.watchwinWidth = int(self.totalW*self.watchwinRatio)
    self.stackwin.w_create('botright '+str(self.stackwinHeight)+' new')
    if self.cliwin:
      self.cliwin.w_create('vertical new')
    self.watchwin.w_create('vertical belowright '+str(self.watchwinWidth)+' new')
    vim.command('1wincmd w') # goto srcview window(nr=1, top-left)
    self.cursign = '1'
    self.set_highlight()
  def reLayout(self):
    if self.stackwin.getHeight() != self.stackwinHeight or self.watchwin.getWidth() != self.watchwinWidth:
      self.stackwin.w_command("resize "+str(self.stackwinHeight))
      self.watchwin.w_command("vertical resize "+str(self.watchwinWidth))
    else:
      vim.command("wincmd _")
      vim.command("wincmd |")

  def set_highlight(self):
    """ set vim highlight of debugger sign """
    vim.command("highlight DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse")
    vim.command("highlight DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse")

  def help(self):
    if vim.eval('exists("t:dbgpavimDebugging")') == '0':
      vim.command('help')
    else:
      if vim.eval('exists("t:dbgpavimHelp")') == '1':
        self.helpwin.w_destroy()
        vim.command('unlet t:dbgpavimHelp')
      else:
        self.helpwin  = HelpWindow('HELP__WINDOW')
        self.stackwin.focus()
        self.helpwin.w_create('vertical new')
        vim.command('let t:dbgpavimHelp=1')

  def update_cli(self):
    self.cliwin.focus()
    vim.command('e')
    vim.command('normal G')

  def u_destroy(self):
    """ destroy windows """
    self.watchwin.w_destroy()
    self.stackwin.w_destroy()
    if self.cliwin:
      self.cliwin.w_destroy()
    vim.command('sign unplace 1')
    vim.command('sign unplace 2')
    self.set_highlight()
    if vim.eval('tabpagenr("$")') == '1':
      vim.command('unlet t:dbgpavimDebugging')
      dbgPavim.updateStatusLine()
    else:
      vim.command('tabclose!')
  def go_srcview(self):
    vim.command('1wincmd w')
  def next_sign(self):
    if self.cursign == '1':
      return '2'
    else:
      return '1'
  def set_srcview(self, file, line):
    """ set srcview windows to file:line and replace current sign """

    self.file = file
    self.go_srcview()
    vim.command('silent edit ' + file)

    vim.command('call DbgpavimBindKeys()')
    if line == 0:
      line = 1
    nextsign = self.next_sign()
    vim.command('sign place ' + nextsign + ' name=current line='+str(line)+' file='+file)
    vim.command('sign unplace ' + self.cursign)
    vim.command('sign jump ' + nextsign + ' file='+file)
    self.cursign = nextsign
    if self.cliwin:
      self.update_cli()

    self.line    = line

class DbgSession(object):
  def __init__(self, sock, address):
    self.latestRes = None
    self.msgid = 0
    self.sock = sock
    self.isWinServer = 0
    self.bptsetlst  = {}
    self.bptsetids  = {}
    self.last_command = 'None'
    self.address = address
    self.retries = 0
    self.closed = False
    self.silent_commmands = {}
  def jump(self, fn, line):
    vim.command("e +"+str(line)+" "+str(fn))
  def handle_response_breakpoint_set(self, res):
    """handle <response command=breakpoint_set> tag
    <responsponse command="breakpoint_set" id="110180001" transaction_id="1"/>"""
    tid = res.get('transaction_id')
    if tid != None:
      tid = int(tid)
      bno = self.bptsetlst[tid]
      del self.bptsetlst[tid]
      self.bptsetids[bno] = res.get('id')
  def getbid(self, bno):
    """ get Debug Server's breakpoint numbered with bno """
    if bno in self.bptsetids:
      return self.bptsetids[bno]
    return None
  def recv_data(self,len):
    c = self.sock.recv(len)
    if c == '':
      self.closed = True
    return c
  def recv_length(self):
    length = ''
    while 1:
      c = self.recv_data(1)
      if c == '\0':
        break
      if c.isdigit():
        length = length + c
    x = 0
    try:
      x = int(length)
    except ValueError:
      DBGPavimTrace("ValueError %s" % (length) )
      self.closed = True
      x = 0
    return x
  def recv_null(self):
    while 1:
      c = self.recv_data(1)
      if c == '\0':
        return
  def recv_body(self, to_recv):
    body = ''
    while to_recv > 0:
      buf = self.recv_data(to_recv)
      to_recv -= len(buf)
      body = body + buf
    return body
  def recv_msg(self):
    length = self.recv_length()
    body = None
    if length:
      body   = self.recv_body(length)
      self.recv_null()
    return body
  def send_msg(self, cmd):
    DBGPavimTrace(str(self.msgid)+">"*16+self.address+"\n"+cmd)
    try:
      self.sock.send(cmd + '\0')
    except socket.timeout, e:
      self.retries = self.retries+1
    except socket.error, e:
      DBGPavimTrace("Exception when send_msg %d from %s: %s" % (self.msgid, self.address, e[0]) )
      self.closed = True
  def handle_recvd_msg(self, res):
    DBGPavimTrace(str(self.msgid)+"<"*16+self.address+"\n"+res)
    try:
      resDom = ET.fromstring(res)
      if resDom.tag == "{urn:debugger_protocol_v1}response":
        if resDom.get('command') == "breakpoint_set":
          self.handle_response_breakpoint_set(resDom)
        if resDom.get('command') == "stop":
          self.s_close()
      elif resDom.tag == "{urn:debugger_protocol_v1}init":
        [fn, self.isWinServer] = getFilePath(resDom.get('fileuri'))
        self.language = resDom.get('language').lower()
    except:
      resDom = None
    return resDom
  def send_command(self, cmd, arg1 = '', arg2 = ''):
    self.msgid = self.msgid + 1
    self.retries = 0
    line = cmd + ' -i ' + str(self.msgid)
    if arg1 != '':
      line = line + ' ' + arg1
    if arg2 != '':
      line = line + ' -- ' + base64.encodestring(arg2)[0:-1]
    self.send_msg(line)
    return self.msgid
  def ack_command(self):
    try:
      self.latestRes = self.recv_msg()
      if self.latestRes == None:
        return None
      resDom = self.handle_recvd_msg(self.latestRes)
      if resDom != None:
        tid = resDom.get('transaction_id')
        if tid != None and int(tid) != int(self.msgid):
          DBGPavimTrace("Unexpected msg %s when waiting for msg %d from %s" % (tid, self.msgid, self.address) )
        if self.retries:
          DBGPavimTrace("Retried %d times for msg %d from %s" % (self.retries, self.msgid, self.address) )
      else:
        DBGPavimTrace("Ignored garbage data from %s" % (self.address) )
        self.closed = True
      return resDom
    except socket.timeout, e:
      self.retries = self.retries+1
      return None
    except socket.error, e:
      DBGPavimTrace("Exception when recv_msg %d from %s: %s" % (self.msgid, self.address, e[0]) )
      return None
  def s_command(self, cmd, arg1 = '', arg2 = '', extra = '0', silent = False):
    if cmd == 'eval':
      if self.language == 'php':
        arg2 = '$evalResult=(%s)' %(arg2)
      else:
        arg2 = 'evalResult=(%s)' %(arg2)
    self.send_command(cmd, arg1, arg2)
    self.last_command = cmd+'('+arg1+','+arg2+','+extra+')'
    if silent:
      self.silent_commmands[self.msgid] = 1
    return self.ack_command()
  def getExtra(self):
    extra = ""
    if self.last_command != None:
      t = self.last_command.split(',')
      extra = t[-1][:-1]
    return extra
  def s_close(self):
    if self.sock:
      self.sock.close()
      self.sock = None
  def init(self):
    self.ack_command()
    if not self.closed:
      for bno in dbgPavim.breakpt.list():
        fn = dbgPavim.remotePathOf(dbgPavim.breakpt.getfile(bno))
        msgid = self.send_command('breakpoint_set', \
                                  '-t line -f ' + fn + ' -n ' + str(dbgPavim.breakpt.getline(bno)) + ' -s enabled', \
                                  dbgPavim.breakpt.getexp(bno))
        self.bptsetlst[msgid] = bno
        self.ack_command()
    return not self.closed

class DbgSessionWithUI(DbgSession):
  def __init__(self, sock, address):
    self.status     = None
    self.ui         = DebugUI(0.3, 0.4)

    self.msgid      = 0
    self.stacks     = []
    self.curstack   = 0
    self.laststack  = 0
    DbgSession.__init__(self,sock,address)

  def s_close(self):
    super(DbgSessionWithUI, self).s_close()
    self.ui.u_destroy()

  def copyFromParent(self, ss):
    self.latestRes = ss.latestRes
    self.msgid = ss.msgid
    self.isWinServer = ss.isWinServer
    self.sock = ss.sock
    self.address = ss.address
    self.language = ss.language
    self.bptsetlst  = ss.bptsetlst
    self.bptsetids  = ss.bptsetids
  def init(self, first_command):
    self.s_command('feature_set', '-n max_children -v ' + dbgPavim.maxChildren)
    self.s_command('feature_set', '-n max_data -v ' + dbgPavim.maxData)
    self.s_command('feature_set', '-n max_depth -v ' + dbgPavim.maxDepth)
    self.s_command(first_command)

  def restart(self):
    if vim.eval('exists("t:dbgpavimDebugging")') == '1':
      vim.command('tabclose')
    self.s_start(self.ui.cliwin)
  def s_start(self, cliwin = None):
    self.sock.settimeout(30)

    self.ui.cliwin = cliwin
    self.ui.u_create(self)
    if self.bap:
      self.handle_recvd_msg(self.latestRes)
      self.init("stack_get")
    else:
      self.init("step_into")

    self.ui.set_srcview(*self.lastPos)
    if self.language == 'php':
      self.s_command('property_get', "-d %d -n $_SERVER['REQUEST_URI']" % (self.laststack), silent = True)
      self.s_command('property_get', "-d %d -n $argv" % (self.laststack), silent = True)
    self.ui.go_srcview()
  def handle_recvd_msg(self, txt):
    # log messages
    txt = txt.replace('\n','')
    txt = txt.replace('<?xml version="1.0" encoding="iso-8859-1"?>', '<?xml version="1.0" encoding="utf-8"?>', 1)
    DBGPavimTrace(str(self.msgid)+"<"*16+self.address+"\n"+txt)
    resDom = ET.fromstring(txt)
    tag = resDom.tag.replace("{urn:debugger_protocol_v1}","")
    """ call appropraite message handler member function, handle_XXX() """
    try:
      handler = getattr(self, 'handle_' + tag)
      handler(resDom)
    except AttributeError:
      print 'Exception when DBGPavim.handle_'+tag+'()'
      DBGPavimTrace(str(sys.exc_info()[1]))
      DBGPavimTrace("".join(traceback.format_tb( sys.exc_info()[2])))
    self.ui.go_srcview()
    return resDom
  def handle_response(self, res):
    """ call appropraite response message handler member function, handle_response_XXX() """
    errors  = res.find('{urn:debugger_protocol_v1}error')
    if errors != None:
      self.handle_response_error(res)
      return

    command = res.get('command')
    try:
      handler = getattr(self, 'handle_response_' + command)
    except AttributeError:
      print 'Exception when DBGPavim.handle_response_'+command+'()'
      DBGPavimTrace(str(sys.exc_info()[1]))
      DBGPavimTrace("".join(traceback.format_tb( sys.exc_info()[2])))
      return
    handler(res)
    return
  def handle_response_stop(self, res):
    dbgPavim.handle_exception(self)

  def handle_init(self, res):
    """handle <init> tag
    <init appid="7035" fileuri="file:///home/segv/htdocs/index.php" language="PHP" protocol_version="1.0">
      <engine version="2.0.0beta1">
        Xdebug
      </engine>
      <author>
        Derick Rethans
      </author>
      <url>
        http://xdebug.org
      </url>
      <copyright>
        Copyright (c) 2002-2004 by Derick Rethans
      </copyright>
    </init>"""

    [fn, self.isWinServer] = getFilePath(res.get('fileuri'))
    self.language = res.get('language').lower()
    self.lastPos = (dbgPavim.localPathOf(fn), 1)
  def handle_response_error(self, res):
    """ handle <error> tag """
    DBGPavimTrace(ET.tostring(res))
    errors  = res.findall('{urn:debugger_protocol_v1}error')
    tid = int(res.get('transaction_id'))
    if tid in self.silent_commmands:
      del self.silent_commmands[tid]
    else:
      for e in errors:
        error_msg = e.find('{urn:debugger_protocol_v1}message')
        self.ui.watchwin.write('%s Error when %s (%d): %s' % (self.ui.watchwin.commenter, self.last_command, tid, error_msg.text))

  def handle_response_stack_get(self, res):
    """handle <response command=stack_get> tag
    <response command="stack_get" transaction_id="1 ">
      <stack filename="file:///home/segv/htdocs/index.php" level="0" lineno="41" where="{main}"/>
    </response>

    for windows
    <response xmlns="urn:debugger_protocol_v1" xmlns:xdebug="http://xdebug.org/dbgp/xdebug" command="stack_get" transaction_id="12">
      <stack where="{main}" level="0" type="file" filename="file:///D:/works/scriptbundle/php/playpen.php" lineno="16">
      </stack>
    </response>
    """
    stacks = res.findall('{urn:debugger_protocol_v1}stack')
    if len(stacks)>0:
      self.curstack  = 0
      self.laststack = len(stacks) - 1

      self.stacks    = []
      for s in stacks:
        [fn, win] = getFilePath(s.get('filename'))
        fn = dbgPavim.localPathOf(fn)
        wr = s.get('where')
        if wr == None:
          wr = "{main}"
        self.stacks.append( {'file':  fn, \
                             'line':  int(s.get('lineno')),  \
                             'where': wr,        \
                             'level': int(s.get('level'))
                             } )

      self.ui.stackwin.clean()
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.stackwin.render(stacks)
      self.lastPos = ( self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'] )
      self.ui.set_srcview( self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'] )

  def handle_response_step_out(self, res):
    """handle <response command=step_out> tag
    <response command="step_out" reason="ok" status="break" transaction_id="1 "/>"""
    if res.get('reason') == 'ok':
      self.status = res.get('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_step_over(self, res):
    """handle <response command=step_over> tag
    <response command="step_over" reason="ok" status="break" transaction_id="1 "/>"""
    if res.get('reason') == 'ok':
      self.status = res.get('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_step_into(self, res):
    """handle <response command=step_into> tag
    <response command="step_into" reason="ok" status="break" transaction_id="1 "/>"""
    if res.get('reason') == 'ok':
      self.status = res.get('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_run(self, res):
    """handle <response command=run> tag
    <response command="step_over" reason="ok" status="break" transaction_id="1 "/>"""
    self.status = res.get('status')
  def handle_response_eval(self, res):
    """handle <response command=eval> tag """
    self.ui.watchwin.render(res)
  def handle_response_property_get(self, res):
    """handle <response command=property_get> tag """
    lineno = self.getExtra()
    self.ui.watchwin.render(res, int(lineno))
  def handle_response_context_get(self, res):
    """handle <response command=context_get> tag """
    self.ui.watchwin.render(res)
  def handle_response_feature_set(self, res):
    """handle <response command=feature_set> tag """
    #self.ui.watchwin.render(res)
  def handle_response_default(self, res):
    """handle <response command=context_get> tag """
    print res.toprettyxml()
  def handle_response_breakpoint_remove(self, res):
    """handle <response command=feature_set> tag """

  def go(self, stack):
    if stack >= 0 and stack <= self.laststack:
      self.curstack = stack
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def jump(self, fn, line):
    self.ui.set_srcview(fn, line)

  def up(self):
    if self.curstack > 0:
      self.curstack -= 1
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def down(self):
    if self.curstack < self.laststack:
      self.curstack += 1
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def property_get(self, name):
    if name == '':
      name = vim.eval('expand("<cword>")')
    elif name == '%v%':
      name = vim.eval('@v')
    if name:
      name = string.replace(name,'"','\'')
      if self.language == 'php' and name[0] != '$':
        name = '$'+name
      if string.find(name,' ') != -1:
        name = "\"" + name +"\""
      self.s_command('property_get', '-d %d -n %s' % (self.curstack,  name))

  def expandVar(self, name):
    (row, col) = vim.current.window.cursor
    if string.find(name,' ') != -1:
      name = "\"" + name +"\""
    self.s_command('property_get', '-d %d -n %s' % (self.curstack,  name), '', str(row))

  def watch_execute(self):
    """ execute command in watch window """
    (cmd, expr) = self.ui.watchwin.get_command()
    if cmd == 'exec':
      self.s_command('exec', '', expr)
      print cmd, '--', expr
    elif cmd == 'eval':
      self.s_command('eval', '', expr)
      print cmd, '--', expr
    else:
      print "no commands", cmd, expr

class DbgSilentClient(Thread):
  def __init__(self, ss):
    self.session = ss
    Thread.__init__(self)
  def run(self):
    DBGPavimTrace("DbgSilentClient started %s!" % (self.session.address))
    self.session.init()
    if not self.session.closed:
      self.session.sock.settimeout(1)
      self.session.send_command('run')
      count = 600
      while dbgPavim.running and count > 0 and not self.session.closed:
        resDom = self.session.ack_command()
        if resDom != None:
          status = resDom.get('status')
          if status == "stopping":
            self.session.s_command("stop")
          elif status == "break":
            dbgPavim.debugListener.newSession(self.session, True)
          break
        else:
          DBGPavimTrace("Invalid responsponse %s!" % (self.session.address))
        count = count-1
    DBGPavimTrace("DbgSilentClient stopped %s!" % (self.session.address))

class DbgListener(Thread):
  (LISTEN,CLOSED) = (0,1)
  """ DBGp Procotol class """
  def __init__(self, port):
    self.port     = port
    self.session_queue = []
    self._status  = self.CLOSED
    self.lock = Lock()
    Thread.__init__(self)
  def l_start(self):
    Thread.start(self)
    time.sleep(0.1)
    dbgPavim.updateStatusLine()
  def pendingCount(self):
    self.lock.acquire()
    c = len(self.session_queue)
    self.lock.release()
    return c
  def newSession(self, ss, bap):
    if not isinstance(ss, DbgSessionWithUI):
      s = DbgSessionWithUI(None,"")
      s.copyFromParent(ss)
      ss = s
    ss.bap = bap
    self.lock.acquire()
    self.session_queue.append(ss)
    c = str(len(self.session_queue))
    self.lock.release()
    dbgPavim.updateStatusLine()
    if dbgPavim.dbgPavimOnce:
      self.stop(False)
    print c+" pending connection(s) to be debug, press "+dbgPavim.dbgPavimKeyRun+" to continue."
  def nextSession(self):
    session = None
    self.lock.acquire()
    if len(self.session_queue) > 0:
      session = self.session_queue.pop(0)
    self.lock.release()
    print ""
    return session
  def stop(self, closeConnection = True):
    self.lock.acquire()
    try:
      if self._status == self.LISTEN:
        client = socket.socket ( socket.AF_INET, socket.SOCK_STREAM )
        client.connect ( ( '127.0.0.1', self.port ) )
        client.close()
    finally:
      if closeConnection:
        for s in self.session_queue:
          s.send_command('detach')
          s.sock.close()
        del self.session_queue[:]
    self._status = self.CLOSED
    self.lock.release()
    dbgPavim.updateStatusLine()
  def status(self):
    self.lock.acquire()
    s = self._status
    self.lock.release()
    return s
  def run(self):
    global dbgPavim
    self.lock.acquire()
    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.settimeout(None)
    try:
      serv.bind(('', self.port))
    except socket.error, e:
      print "Can not bind to port "+str(self.port)+', Socket Error '+str(e[0])
      self.lock.release()
      return
    print ""
    serv.listen(5)
    self._status = self.LISTEN
    self.lock.release()
    DBGPavimTrace("DbgListener started at %d!" % (self.port))
    while 1:
      (sock, address) = serv.accept()
      adr = '%s:%d' % (address[0], address[1])
      DBGPavimTrace('# Connection from %s\n' % adr)
      s = self.status()
      if s == self.LISTEN:
        if dbgPavim.breakAtEntry:
          ss = DbgSessionWithUI(sock, adr)
          if DbgSession.init(ss):
            self.newSession(ss, False)
        else:
          client = DbgSilentClient(DbgSession(sock, adr))
          client.start()
      else:
        break
    serv.close()
    DBGPavimTrace("DbgListener stopped at %d!" % (self.port))

class BreakPoint:
  """ Breakpoint class """
  def __init__(self):
    """ initalize """
    self.dictionaries  = {}
    self.startbno = 10000
    self.maxbno   = self.startbno
  def clear(self):
    """ clear of breakpoint number """
    self.dictionaries.clear()
    self.maxbno = self.startbno
  def add(self, file, line, exp = ''):
    """ add break point at file:line """
    self.maxbno = self.maxbno + 1
    self.dictionaries[self.maxbno] = { 'file':file, 'line':line, 'exp':exp }
    return self.maxbno
  def remove(self, bno):
    """ remove break point numbered with bno """
    del self.dictionaries[bno]
  def find(self, file, line):
    """ find break point and return bno(breakpoint number) """
    signs = vim.eval('DbgpavimSigns()')
    for k in signs.keys():
      if signs[k][0] == file and signs[k][1] == line:
        bno = int(k)
        self.dictionaries[bno]['file'] = file
        self.dictionaries[bno]['line'] = line
        return bno
    return None
  def getfile(self, bno):
    """ get file name of breakpoint numbered with bno """
    return self.dictionaries[bno]['file']
  def getline(self, bno):
    """ get line number of breakpoint numbered with bno """
    return self.dictionaries[bno]['line']
  def getexp(self, bno):
    """ get expression of breakpoint numbered with bno """
    return self.dictionaries[bno]['exp']
  def list(self):
    """ return list of breakpoint number """
    return self.dictionaries.keys()

class AsyncRunner(Thread):
  def __init__(self, cmd, logfile):
    self.cmd = cmd
    self.logfile = logfile
    Thread.__init__(self)
  def run(self):
    log = open(self.logfile, "w")
    subprocess.check_call(self.cmd, stdin=None, stdout=log, stderr=log, shell=True)
    log.close()
    os.remove(self.logfile)

class DBGPavim:
  """ Main DBGPavim class """
  def __init__(self):
    """ initialize DBGPavim """
    self.loadSettings()
    self.debugListener = DbgListener(self.port)
    vim.command('sign unplace *')

    self.normal_statusline = vim.eval('&statusline')
    self.statusline="%<%f\ %h%m%r\ %=%-10.(%l,%c%V%)\ %P\ %=%{(g:dbgPavimBreakAtEntry==1)?'bae':'bap'}"
    self.breakpt    = BreakPoint()
    self.breakold   = BreakPoint()
    self.watchList  = []
    self.evalList  = []
    self.running   = True
    self.debugSessions = {}
    self.cliwin = None

  def updateStatusLine(self):
    if vim.eval('exists("t:dbgpavimDebugging")') == '1':
      sl = self.statusline+"%{'-CONN'}"
    else:
      status = self.debugListener.status()
      c = self.debugListener.pendingCount()
      if c > 0:
        sl = self.statusline+"%{'-PEND-"+str(c)+"'}"
      elif status == DbgListener.LISTEN:
        sl = self.statusline+"%{'-LISN-"+str(self.port)+"'}"
      else:
        sl = self.normal_statusline
    vim.command("let &statusline=\""+sl+"\"")

  def loadSettings(self):
    self.port = int(vim.eval('g:dbgPavimPort'))
    self.dbgPavimKeyRun = vim.eval('g:dbgPavimKeyRun')
    self.maxChildren = vim.eval('g:dbgPavimMaxChildren')
    self.maxData = vim.eval('g:dbgPavimMaxData')
    self.maxDepth = vim.eval('g:dbgPavimMaxDepth')
    self.breakAtEntry = int(vim.eval('g:dbgPavimBreakAtEntry'))
    self.showContext = int(vim.eval('g:dbgPavimShowContext'))
    self.pathMap = vim.eval('g:dbgPavimPathMap')
    self.dbgPavimOnce = int(vim.eval('g:dbgPavimOnce'))
    for m in self.pathMap:
      m[0] = m[0].replace("\\","/")
      m[1] = m[1].replace("\\","/")
  def remotePathOf(self,lpath):
    for m in self.pathMap:
      l = len(m[0])
      if l and lpath[0:l] == m[0]:
        return m[1]+lpath[l:]
    fn = lpath
    if fn[:7] != "file://":
      fn = fn.replace("\\","/")
      if fn[1] == ':':
        fn = "file:///"+fn
      else:
        fn = "file://"+fn
      lpath = fn
    return lpath
  def localPathOf(self,rpath):
    for m in self.pathMap:
      l = len(m[1])
      if l and rpath[0:l] == m[1]:
        return m[0]+rpath[l:]
    return rpath
  def setMaxChildren(self):
    self.maxChildren = vim.eval('g:dbgPavimMaxChildren')
    for k in self.debugSessions.keys():
      self.debugSessions[k].s_command('feature_set', '-n max_children -v ' + self.maxChildren)
  def setMaxDepth(self):
    self.maxDepth = vim.eval('g:dbgPavimMaxDepth')
    for k in self.debugSessions.keys():
      self.debugSessions[k].s_command('feature_set', '-n max_depth -v ' + self.maxDepth)
  def setMaxData(self):
    self.maxData = vim.eval('g:dbgPavimMaxData')
    for k in self.debugSessions.keys():
      self.debugSessions[k].s_command('feature_set', '-n max_data -v ' + self.maxData)
  def handle_exception(self, currentSession):
    DBGPavimTrace(str(sys.exc_info()[1]))
    DBGPavimTrace("".join(traceback.format_tb( sys.exc_info()[2])))
    errno = sys.exc_info()[0]

    session = self.debugListener.nextSession()
    if errno == socket.timeout:
      if session != None:
        print "socket timeout, switch to another session."
        ss = DbgSession(currentSession.sock, currentSession.address)
        ss.latestRes = currentSession.latestRes
        client = DbgSilentClient(ss)
        client.start()
        del self.debugSessions[currentSession.address]
        self.debugSessions[session.address] = session
        session.s_start()
      else:
        print "socket timeout, try again or press F6 to stop debugging."
    else: #errno == socket.error:
      del self.debugSessions[currentSession.address]
      currentSession.s_close()
      if session != None:
        self.debugSessions[session.address] = session
        session.s_start()
    self.updateStatusLine()

  def getCurrentSession(self):
    ss = None
    if vim.eval('exists("t:dbgpavimDebugging")') == '1':
      k = vim.eval('t:dbgpavimDebugging')
      if k in self.debugSessions:
        ss = self.debugSessions[k]
    return ss

  def session_command(self, *args):
    ss = self.getCurrentSession()
    if ss:
      if hasattr(ss, args[0]):
        handler = getattr(ss, args[0])
      else:
        handler = getattr(ss.ui, args[0])
      handler(*args[1:])

  def step(self):
    ss = self.getCurrentSession()
    if ss:
      ss.s_command('stack_get')
      if self.showContext:
        ss.s_command('context_get', ('-d %d' % ss.curstack))
      for var in self.watchList:
        ss.s_command('property_get', "-d %d -n %s" % (ss.curstack, var))
      for expr in self.evalList:
        ss.s_command('eval', '', expr)
  def d_command(self, msg, arg1 = '', arg2 = ''):
    try:
      ss = self.getCurrentSession()
      if ss:
        ss.s_command(msg, arg1, arg2)
        if ss.status != 'stopping':
          self.step()
        else:
          ss.s_command('stop')
      else:
        print 'No debug session started.'
    except:
      self.handle_exception(ss)
  def context(self):
    ss = self.getCurrentSession()
    if ss:
      ss.s_command('context_get', ('-d %d' % ss.curstack))
  def watch_input(self, cmd, arg = ''):
    ss = self.getCurrentSession()
    if ss:
      ss.ui.watchwin.input(cmd, arg)
  def watch(self, name = ''):
    if name == '':
      self.showContext = not self.showContext
    else:
      if name in self.watchList:
        self.watchList.remove(name)
      else:
        self.watchList.append(name)
  def eval(self, name = ''):
    if name == '':
      print "Please follow an expression that you'd like to be evaluated automatically after each step."
    else:
      if name in self.evalList:
        self.evalList.remove(name)
      else:
        self.evalList.append(name)
  def listWatch(self):
    if self.showContext:
      print '*CONTEXT*'
    for var in self.watchList:
      print var
    for exp in self.evalList:
      print exp+'(eval)'

  def run(self):
    """ start debugger or continue """
    try:
      ss = self.getCurrentSession()
      if ss:
        ss.s_command('run')
        if ss.status == 'stopping':
          ss.s_command("stop")
        elif ss.status != 'stopped':
          self.step()
      else:
        lstatus = self.debugListener.status()
        ss = self.debugListener.nextSession()
        if ss:
          self.debugSessions[ss.address] = ss
          ss.s_start(self.cliwin)
          self.cliwin = None
        elif lstatus == DbgListener.CLOSED:
          self.running   = True
          self.loadSettings()
          self.debugListener = DbgListener(self.port)
          self.debugListener.l_start()
    except:
      self.handle_exception(ss)

  def cli(self, args=""):
    vim.command("let g:dbgPavimBreakAtEntry=1")
    filetype = vim.eval('&filetype')
    filename = vim.eval('expand("%")')
    if filename:
      cmd = ' '+filename+' '+args
      if filetype == 'php':
        if vim.eval('DbgpavimCheckXdebug()') == '0':
          cmd = 'php -dxdebug.remote_autostart=1 -dxdebug.remote_port='+str(self.port)+cmd
      elif filetype == 'python':
        if vim.eval('DbgpavimCheckPydbgp()') == '0':
          cmd = 'pydbgp -u -d '+str(self.port)+cmd
      else:
        print "Only python and php file debugging are integrated for now."
      if cmd[0] != ' ':
        clilog = os.getenv("HOME").replace("\\","/")+"/.dbgpavim.cli"
        self.cliwin = ConsoleWindow(clilog)
        self.run()
        self.dp = True
        ar = AsyncRunner(cmd, clilog)
        ar.start()
        time.sleep(0.4)
        #vim.eval('feedkeys("\\'+self.dbgPavimKeyRun+'")')
    else:
      print "You need open one python or php file first."

  def list(self):
    vim.command("lgetexpr []")
    inCount = 0
    for bno in self.breakpt.list():
      inCount = inCount + 1
      if self.breakpt.getexp(bno) != '':
        vim.command("lad '"+"\|condition: "+self.breakpt.getexp(bno)+" \| "+self.breakpt.getfile(bno)+":"+str(self.breakpt.getline(bno))+":1'")
      else:
        vim.command("lad '"+self.breakpt.getfile(bno)+":"+str(self.breakpt.getline(bno))+":1'")
    vim.command("lw")
    if inCount > 0 :
      vim.command("wincmd j")
      vim.command("resize 10")

  def removeBreakPoint(self, bno):
    ss = self.getCurrentSession()
    if ss:
      id = ss.getbid(bno)
      if ss != None and id != None:
        ss.s_command('breakpoint_remove', '-d ' + str(id))

  def setBreakPoint(self, bno):
    ss = self.getCurrentSession()
    if ss:
      fn = dbgPavim.remotePathOf(self.breakpt.getfile(bno))
      msgid = ss.send_command('breakpoint_set', \
                                '-t line -f ' + fn + ' -n ' + str(self.breakpt.getline(bno)), \
                                self.breakpt.getexp(bno))
      ss.bptsetlst[msgid] = bno
      ss.ack_command()

  def clear(self):
    for bno in self.breakpt.list():
      self.breakold.add(self.breakpt.getfile(bno), self.breakpt.getline(bno), self.breakpt.getexp(bno))
      vim.command('sign unplace ' + str(bno))
      self.removeBreakPoint(bno)
      self.breakpt.remove(bno)

  def unclear(self):
    for bno in self.breakold.list():
      row = self.breakold.getline(bno)
      file = self.breakold.getfile(bno)
      exp = self.breakold.getexp(bno)
      self.breakold.remove(bno)
      inbno = self.breakpt.find(file, str(row))
      if inbno == None:
        inbno = self.breakpt.add(file, row, exp)
        vim.command('sign place ' + str(inbno) + ' name=breakpt line=' + str(row) + ' file=' + file)
        self.setBreakPoint(inbno)

  def mark(self, exp = ''):
    (row, col) = vim.current.window.cursor
    file       = vim.current.buffer.name

    if file:
      bno = self.breakpt.find(file, str(row))
      ss = self.getCurrentSession()
      if bno != None:
        self.breakpt.remove(bno)
        vim.command('sign unplace ' + str(bno))
        self.removeBreakPoint(bno)
      else:
        bno = self.breakpt.add(file, row, exp)
        vim.command('sign place ' + str(bno) + ' name=breakpt line=' + str(row) + ' file=' + file)
        self.setBreakPoint(bno)

  def closeCurrentSession(self):
    ss = self.getCurrentSession()
    if ss:
      del self.debugSessions[ss.address]
      ss.send_command('detach')
      ss.s_close()

  def quit(self):
    ss = self.getCurrentSession()
    if ss:
      del self.debugSessions[ss.address]
      ss.send_command('detach')
      ss.s_close()
    else:
      self.running = False
      self.debugListener.stop()

def dbgPavim_init():
  global dbgPavim
  dbgPavim = DBGPavim()

error_msg = { \
    # 000 Command parsing errors
    0   : """no error""",                                                                                                                                                      \
    1   : """parse error in command""",                                                                                                                                        \
    2   : """duplicate arguments in command""",                                                                                                                                \
    3   : """invalid options (ie, missing a required option)""",                                                                                                               \
    4   : """Unimplemented command""",                                                                                                                                         \
    5   : """Command not available (Is used for async commands. For instance if the engine is in state "run" than only "break" and "status" are available). """,               \
    # 100 : File related errors
    100 : """can not open file (as a reply to a "source" command if the requested source file can't be opened)""",                                                             \
    101 : """stream redirect failed """,                                                                                                                                       \
    # 200 Breakpoint, or code flow errors
    200 : """breakpoint could not be set (for some reason the breakpoint could not be set due to problems registering it)""",                                                  \
    201 : """breakpoint type not supported (for example I don't support 'watch' yet and thus return this error)""",                                                            \
    202 : """invalid breakpoint (the IDE tried to set a breakpoint on a line that does not exist in the file (ie "line 0" or lines past the end of the file)""",               \
    203 : """no code on breakpoint line (the IDE tried to set a breakpoint on a line which does not have any executable code. The debugger engine is NOT required to """     + \
          """return this type if it is impossible to determine if there is code on a given location. (For example, in the PHP debugger backend this will only be """         + \
          """returned in some special cases where the current scope falls into the scope of the breakpoint to be set)).""",                                                    \
    204 : """Invalid breakpoint state (using an unsupported breakpoint state was attempted)""",                                                                                                                                                      \
    205 : """No such breakpoint (used in breakpoint_get etc. to show that there is no breakpoint with the given ID)""",                                                        \
    206 : """Error evaluating code (use from eval() (or perhaps property_get for a full name get))""",                                                                         \
    207 : """Invalid expression (the expression used for a non-eval() was invalid) """,                                                                                        \
    # 300 Data errors
    300 : """Can not get property (when the requested property to get did not exist, this is NOT used for an existing but uninitialized property, which just gets the """    + \
          """type "uninitialised" (See: PreferredTypeNames)).""",                                                                                                              \
    301 : """Stack depth invalid (the -d stack depth parameter did not exist (ie, there were less stack elements than the number requested) or the parameter was < 0)""",      \
    302 : """Context invalid (an non existing context was requested) """,                                                                                                      \
    # 900 Protocol errors
    900 : """Encoding not supported""",                                                                                                                                        \
    998 : """An internal exception in the debugger occurred""",                                                                                                                \
    999 : """Unknown error """                                                                                                                                                 \
}
