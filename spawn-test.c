#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "vterm/c-sources/spawn.h"

int main(int argc, char **argv, char **envp)
{
    char *error;
    /* TODO parse args, do fds */
    (void)argc;
    error = vterm_py_spawn_and_forget(argv[1], argv + 1, envp, 0, NULL, -1);
    if (error)
    {
        puts(error);
        free(error);
        return 127;
    }
    return 0;
}
