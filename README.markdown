This is a plugin to enable php debug in VIM with Xdebug, which originates from http://www.vim.org/scripts/script.php?script_id=1152.
But most of the code, especially the debugger engine has been rewritten.


## The enhancements are --

### Non blocking debugger engine.
So that VIM users do not need to wait for connection from apache server. No timeout things, users press F5 to start debugger engine, and uses his/her VIM normally. Debug engine won't stop users to interact with VIM. Users can press F6 to stop debugger engine anytime.

### Catch all connections from apache server.
This is very important for a large website, especially for thoes pages who contain AJAX requests. In that case, one reload of a page may trigger dozens of http request, each of them goes to a different URL. The new debugger engine will catch all connections from apache server. Users can debug all of them without missing anyone.

### Break only at breakpoints

    let g:debuggerBreakAtEntry = 0

    The setting will cause debugger engine to break only at breakpoints. Default value is 1, which means it works like before, the debugger engine breaks at entry.

### new commands and function keys

In normal mode

    <F5>      => start debugger engine
    <F6>      => stop debugger engine
    <F8>      => toggle debuggerBreakAtEntry, when g:debuggerBreakAtEntry=0, debugger engine breaks only at breakpoints.

    Bl        => to list all breakpoints
    Bp        => toggle breakpoint on current line

In debuggin mode 

    <F1>      => toggle help window
    <F2>      => step into 
    <F3>      => step over 
    <F4>      => step out 
    <F5>      => start debugging / run
    <F6>      => stop debugging 
    <F7>      => evalute expression and display result. cursor is automatically move to watch window. type line and just press enter. 
    <F9>      => toggle layout
    <F11>     => shows all variables 
    <F12>     => shows variable on current cursor 

    :Pg        => to print value of complex variables like $this->savings[3]
    :Up        => goto upper level of stack 
    :Dn        => goto lower level of stack 

In Watch window

    If you press Enter key at a line which ends with --
    
    (object)  => to get value of an object.
    (array)   => to get value of an array.

    If you press Enter key at a line of output from command :Bl, that breakpoint will be located.

In Stack window

    If you press Enter key at a line, stack level will be set.

### Windows Support

### Status line for debugger engine

    After user press <F5> to start debugger engine, a string like "PHP-bae-LISN" will show up at the right side of status line.

    The status string looks like -- 

    PHP-<bae|bap>-<LISN|PENDn|CONN|CLSD>

    bae       => means Break At Entry
    bap       => means Break only At breakPoints

    LISN      => means the debugger engine is listening.
    PENDn     => means there are n connections waiting for debugging.
    CONN      => means debug session has been established, and being debugged.
    CLSD      => means the debugger engine has stopped.


## Usage

* Make sure your vim has python(at least 2.3) supported, in vim with command

    <pre>
    :version
    </pre>

    In case of your VIM don't support python, download VIM source package from http://www.vim.org/download.php, then build your own VIM with commands --

    <pre>
    ./configure --prefix=/opt/vim --enable-pythoninterp --with-python-config-dir=/usr/lib/python2.4/config
    make
    make install
    </pre>

* Install xdebug for php, and edit php.ini

    <pre>
    zend_extension=path_to_xdebug.so
    xdebug.remote_enable=1
    </pre>

* Edit your ~/.vimrc

    <pre>
    let g:debuggerPort = 6789
    let g:debuggerBreakAtEntry = 0
    </pre>

* Edit your apche configure file

    In your VirtualHost section, set debugger port same as the one in your vimrc

    <pre>
    php_value xdebug.remote_port 6789
    </pre>

* Save debugger.py and debugger.vim to your ~/.vimr/plugin

* Open your php file, use :Bp to set breakpoints

* Now, press F5 to start debugger engine

* Back to your browser, add XDEBUG_SESSION_START=1 to your URL, for example, http://localhost/index.php?XDEBUG_SESSION_START=1. If you would like to debug from CLI, start your php script like 

    <pre>
    php -dxdebug.remote_autostart=1 -dxdebug.remote_port 6789 test.php
    </pre>
