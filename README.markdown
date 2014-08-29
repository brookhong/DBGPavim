This is a VIM plugin to enable php debuging with Xdebug, to enable python debugging with Komodo-PythonRemoteDebugging-Client, which originates from http://www.vim.org/scripts/script.php?script_id=1152.
But most of the code, especially the debugger backend has been rewritten.

Generally speaking, this is a plugin to make VIM working as a DBGP server, so that VIM can talk with DBGP clients like Xdebug and Komodo.

PHP debugging Tested with:

* XDebug 2.2 - PHP 5.4 - GVIM 7.3 - Python 2.7 @ Windows 7
* XDebug 2.0 - PHP 5.2 - VIM 7.3  - Python 2.7 @ Linux
* XDebug 2.2 - PHP 5.2 - VIM 7.3  - Python 2.7 @ Linux
* XDebug 2.0 - PHP 5.2 - VIM 7.3  - Python 2.3 @ Linux (Only early version of this plugin works with python2.3)
* XDebug 2.1 - PHP 5.3 - MacVIM 7.3  - Python 2.7 @ OS X 10.8

Python debugging Tested with:

* Komodo Python Remote Debugging Client - Python 2.7 - MacVIM 7.3 @ Mac OS X 10.8
* Komodo Python Remote Debugging Client - Python 2.7 - GVIM 7.3 @ Windows 7
* Komodo Python Remote Debugging Client - Python 2.7 - VIM 7.3 @ Linux

Screen shot
----------
Debugging PHP
![DBGPavim-php](http://sharing-from-brook.16002.n6.nabble.com/file/n4930670/debug_mode1.png)
Debugging Python
![DBGPavim-python](http://sharing-from-brook.16002.n6.nabble.com/file/n4930670/py.png)

More at http://sharing-from-brook.16002.n6.nabble.com/Debug-php-in-VIM-with-Xdebug-and-DBGPavim-td4930670.html.


## Enhancements

### Non blocking debugger backend.
So that VIM users do not need to wait for connection from server. No timeouts; users press `F5` to start debugger backend and use VIM normally. Debug backend won't stop users from interacting with VIM. Users can press `F6` to stop debugger backend at any time.

### Catch all connections from apache server.
This is very important for a large website, especially for pages that contain AJAX requests. In that case, one reload of a page may trigger dozens of HTTP requests, each of them going to a different URL. The new debugger backend will catch all connections from the server.

If you would not like catch all connections from HTTP server, then add below line to your vimrc:

    let g:dbgPavimOnce = 1

This setting makes your site accessible when you're in debugging. By default, your site is blocked when you're in debugging, because all connections are caught by debugger backend.


### Break only at breakpoints

The debugger backend breaks only at breakpoints by default. If you would like the debugger backend to break at entry, then add below line to your vimrc:

    let g:dbgPavimBreakAtEntry = 1

### Debug multiple different sessions simultaneously in diffrent tabs

If there are multiple connections to your server at the same time, you can debug all of them simultaneously in different tabs.

The below screencast demos the debugging of two different sessions: one for PHP within Apache, another for Python CLI.

![DBGPavim-simultaneously](https://raw.githubusercontent.com/brookhong/brookhong.github.io/master/assets/images/DBGPavim.gif)

### New commands and function keys

In normal mode

    <F5>      => start debugger backend
    <F6>      => stop debugger backend
    <F8>      => toggle dbgPavimBreakAtEntry, when g:dbgPavimBreakAtEntry=0, debugger backend breaks only at breakpoints.
    <F10>     => toggle breakpoint at current line

    :Bl        => to list all breakpoints
    :Bp [expr] => toggle breakpoint on current line, if expr is provided, that is conditional breakpoint, for example, `:Bp ($i > 3)` only breaks when $i is larger than 3.
    :Dp [args] => to debug current file from CLI, it will run 'php -dxdebug.remote_autostart=1 -dxdebug.remote_port=<your_port> <curret_file_in_vim> [args]'


    :Wc [$foo] => to toggle watch on variable $foo, if no parameter is provided, it will toggle watch on CONTEXT.
    :We [foo]  => to eval expression `foo` automatically after each step.
    :Wl        => to list all watched variables. By default, you can get output like *CONTEXT*, which means context are automatically populated each step in WATCH WINDOW.

In debugging mode

    <F1>      => toggle help window
    <F2>      => step into
    <F3>      => step over
    <F4>      => step out
    <F5>      => start debugging / run
    <F6>      => stop debugging
    <F7>      => evalute expression and display result. cursor is automatically move to watch window. type line and just press `Enter`.
    <F9>      => toggle layout
    <F11>     => shows all variables
    <F12>     => shows variable on current cursor

You can define your own key mappings as below:

    let g:dbgPavimKeyRun = '<F8>'
    let g:dbgPavimKeyStepOver = '<F10>'
    let g:dbgPavimKeyStepInto = '<F11>'
    let g:dbgPavimKeyStepOut = '<F12>'
    let g:dbgPavimKeyPropertyGet = '<F3>'
    let g:dbgPavimKeyContextGet = '<F4>'
    let g:dbgPavimKeyToggleBp = '<F9>'
    let g:dbgPavimKeyToggleBae = '<F5>'
    let g:dbgPavimKeyRelayout = '<F2>'

    :Pg        => to print value of complex variables like $this->savings[3]
    :Up        => goto upper level of stack
    :Dn        => goto lower level of stack

In Watch window

    If you press `Enter` at a line which ends with plus to expand it.

    If you press `Enter` at a line of output from command `:Bl`, that breakpoint will be located.

In Stack window

    If you press `Enter` at a line, stack level will be set.

### Windows Support

### Status line for debugger backend

After user press `F5` to start debugger backend, a string like "bap-LISN-9000" will show up at the right side of status line.
Here `9000` is the listening port of debugger, which is set by g:dbgPavimPort.

The status string looks like:

    <bae|bap>-<LISN|PENDn|CONN|CLSD>

    bae       => means Break At Entry
    bap       => means Break only At breakPoints

    LISN      => means the debugger backend is listening.
    PENDn     => means there are n connections waiting for debugging.
    CONN      => means debug session has been established, and being debugged.
    CLSD      => means the debugger backend has stopped.

### New layout of windows

### Remote debugging

In case that you need run VIM on a different machine from server where apache httpd runs, configuration for DBGPavim:

    let g:dbgPavimPathMap = [['D:/works/php','/var/www'],]

A change to the Apache configuration is also necessary:

    php_value xdebug.remote_host <ip_address_where_you_run_vim>

## Usage

* Make sure your vim has python (at least 2.3) supported. To check, run `:version` in vim.

If your VIM doesn't support python, download VIM source package from http://www.vim.org/download.php, then build your own VIM:

    ./configure --prefix=/opt/vim --enable-pythoninterp --with-python-config-dir=/usr/lib/python2.4/config
    make
    make install

* Install xdebug for php, and edit php.ini

    <pre>
    zend_extension=path_to_xdebug.so
    xdebug.remote_enable=1
    </pre>

* Edit your ~/.vimrc

    <pre>
    let g:dbgPavimPort = 9009
    let g:dbgPavimBreakAtEntry = 0
    </pre>

* Edit your apche configure file

In your VirtualHost section, set debugger port same as the one in your vimrc:

    php_value xdebug.remote_port 9009

* Save dbgpavim.py and dbgpavim.vim to your ~/.vim/plugin

* Open your php file, use :Bp to set breakpoints

* Now, press `F5` to start debugger backend

* Back to your browser, add XDEBUG_SESSION_START=1 to your URL, for example, http://localhost/index.php?XDEBUG_SESSION_START=1.

If you are tired of adding XDEBUG_SESSION_START=1 in query string, there is a XDEBUG_SESSION helper at http://userscripts.org/scripts/review/132695, a user script for Google Chrome. It also works for Firefox via GreaseMonkey.

Or modify your apache configuration (httpd.conf) --

    <VirtualHost>
      ...
      php_value xdebug.remote_port 9009
      php_value xdebug.remote_autostart 1
    </VirtualHost>

## CLI debugging

* If you would like to debug from CLI, start your php script like

    php -dxdebug.remote_autostart=1 -dxdebug.remote_port=9009 test.php

* There is new command `:Dp` to debug current file:

    php -dxdebug.remote_autostart=1 -dxdebug.remote_port=9009

## Python debugging
DBGPavim is both a DBGP protocol server and VIM debugger backend, so it can help to debug Python code.

I haved tried it with:

* Komodo Python Remote Debugging Client --Python 2.7 - MacVim 7.3 @ Mac OS X 10.8

1. Download Komodo Python Remote Debugging Client from http://code.activestate.com/komodo/remotedebugging/, for Mac, it's Komodo-PythonRemoteDebugging-7.1.2-73175-macosx-x86.tar.gz (Refer to http://docs.activestate.com/komodo/4.4/debugpython.html)

2. Open the python script file with VIM, and Press <F5> to listen.

3. extract the package, and run

    bin/pydbgp -d 127.0.0.1:9000 /works/scriptbundle/python/playpen.py

4. then the others are same as php debugging.
