#pragma once

char *vterm_py_spawn_and_forget(char *cmd, char **argv, char **envp, int nfds, int *fds, int tty_fd);
