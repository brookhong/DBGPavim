" DBGp client: a remote debugger interface to the DBGp protocol
"
" Script Info and Documentation  {{{
"=============================================================================
"    Copyright: Copyright (C) 2012 Brook Hong
"      License:	The MIT License
"				
"				Permission is hereby granted, free of charge, to any person obtaining
"				a copy of this software and associated documentation files
"				(the "Software"), to deal in the Software without restriction,
"				including without limitation the rights to use, copy, modify,
"				merge, publish, distribute, sublicense, and/or sell copies of the
"				Software, and to permit persons to whom the Software is furnished
"				to do so, subject to the following conditions:
"				
"				The above copyright notice and this permission notice shall be included
"				in all copies or substantial portions of the Software.
"				
"				THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
"				OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
"				MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"				IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
"				CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
"				TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
"				SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
" Name Of File: debugger.vim, debugger.py
"  Description: remote debugger interface to DBGp protocol
"               The DBGPavim originates from http://www.vim.org/scripts/script.php?script_id=1152 and http://www.vim.org/scripts/script.php?script_id=1929, with a new enhanced debugger engine.
 
"   Maintainer: hzgmaxwell <at> hotmail <dot> com
"
"               This file should reside in the plugins directory along
"               with debugger.py and be automatically sourced.
"               
"               By default, the script expects the debugging engine to connect
"               on port 9000. You can change this with the g:debuggerPort
"               variable by putting the following line your vimrc:
"
"                 let g:debuggerPort = 10001
"
"               where 10001 is the new port number you want the server to
"               connect to.
"
"               There are three maximum limits you can set referring to the
"               properties (variables) returned by the debugging engine.
"
"               g:debuggerMaxChildren (default 32): The max number of array or
"               object children to initially retrieve per variable.
"               For example:
"
"                 let g:debuggerMaxChildren = 64
"
"               g:debuggerMaxData (default 1024 bytes): The max amount of
"               variable data to retrieve.
"               For example:
"
"                 let g:debuggerMaxData = 2048
"
"               g:debuggerMaxDepth (default 1): The maximum depth that the
"               debugger engine may return when sending arrays, hashs or
"               object structures to the IDE.
"               For example:
"
"                 let g:debuggerMaxDepth = 10
"
"               g:debuggerBreakAtEntry (default 1): Whether to break at entry,
"               if set it 0, the debugger engine will break only at
"               breakpoints.
"               For example:
"
"                 let g:debuggerBreakAtEntry = 0
"
"=============================================================================
" }}}
" php -dxdebug.remote_autostart=1 test.php
" Do not source this script when python is not compiled in.
if !has("python")
    finish
endif

" Load debugger.py either from the same path where debugger.vim is
let s:debugger_py = expand("<sfile>:p:h")."/debugger.py"
if filereadable(s:debugger_py)
  exec 'pyfile '.s:debugger_py
else
  call confirm('debugger.vim: Unable to find '.s:debugger_py.'. Place it in either your home vim directory or in the Vim runtime directory.', 'OK')
endif

map <F1> :python debugger.resize()<cr>
map <F2> :python debugger.command('step_into')<cr>
map <F3> :python debugger.command('step_over')<cr>
map <F4> :python debugger.command('step_out')<cr>

map <Leader>dr :python debugger.resize()<cr>
map <Leader>di :python debugger.command('step_into')<cr>
map <Leader>do :python debugger.command('step_over')<cr>
map <Leader>dt :python debugger.command('step_out')<cr>

nnoremap ,pe :python debugger.watch_input("eval")<cr>A

map <F5> :python debugger.run()<cr>
map <F6> :python debugger.quit()<cr>

map <F7> :python debugger.command('step_into')<cr>
map <F8> :python debugger.command('step_over')<cr>
map <F9> :python debugger.command('step_out')<cr>

map <F11> :python debugger.context('context_get')<cr>
map <F12> :python debugger.property()<cr>
map <F11> :python debugger.watch_input("context_get")<cr>A<cr>
map <F12> :python debugger.watch_input("property_get", '<cword>')<cr>A<cr>

hi DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse
hi DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse
function! Bae(val)
  let g:debuggerBreakAtEntry = a:val
  execute 'python debugger.break_at_entry = '.a:val
endfunction
command! -nargs=1 Bae :call Bae('<args>')
command! -nargs=? Bp python debugger.mark('<args>')
command! -nargs=0 Bl python debugger.list()
command! -nargs=? Pg python debugger.property("<args>")
command! -nargs=0 Up python debugger.up()
command! -nargs=0 Dn python debugger.down()
sign define current text=->  texthl=DbgCurrent linehl=DbgCurrent
sign define breakpt text=B>  texthl=DbgBreakPt linehl=DbgBreakPt
if !exists('g:debuggerPort')
  let g:debuggerPort = 9000
endif
if !exists('g:debuggerMaxChildren')
  let g:debuggerMaxChildren = 32
endif
if !exists('g:debuggerMaxData')
  let g:debuggerMaxData = 1024
endif
if !exists('g:debuggerMaxDepth')
  let g:debuggerMaxDepth = 1
endif
if !exists('g:debuggerBreakAtEntry')
  let g:debuggerBreakAtEntry = 1
endif
python debugger_init()
set laststatus=2
autocmd VimLeavePre * python debugger.quit()
