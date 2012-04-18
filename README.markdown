This is a plugin to enable php debug in VIM with Xdebug, which is based on
http://www.vim.org/scripts/script.php?script_id=1152
http://www.vim.org/scripts/script.php?script_id=1929

My enhancements are --

* Non blocking debug engine.
So that VIM users do not need to wait for connection from apache server. No timeout things, users press <F5> to start debug engine, and uses his/her VIM normally. Debug engine won't stop users to interact with VIM. Users can press <F6> to stop debug engine anytime.

* Catch all connections from apache server.
This is very important for a large website, especially for thoes pages who contain AJAX requests. In that case, one reload of a page may trigger dozens of http request, each of them goes to a different URL. The new debug engine will catch all connections from apache server. Users can debug all of them without missing anyone.

* Other new commands
:Pg         => to print value of complex variables like $this->savings[3]
:Bl         => to list all breakpoints

* Windows Support
