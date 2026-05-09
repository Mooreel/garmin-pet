#include <libmtp.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static uint32_t first_storage_id(LIBMTP_mtpdevice_t *device) {
    if (device->storage == NULL) {
        LIBMTP_Get_Storage(device, LIBMTP_STORAGE_SORTBY_NOTSORTED);
    }
    if (device->storage == NULL) {
        return 0;
    }
    return device->storage->id;
}

static LIBMTP_folder_t *find_child(LIBMTP_folder_t *folder, const char *name) {
    for (LIBMTP_folder_t *item = folder; item != NULL; item = item->sibling) {
        if (item->name != NULL && strcmp(item->name, name) == 0) {
            return item;
        }
    }
    return NULL;
}

static LIBMTP_folder_t *find_folder_path(LIBMTP_folder_t *folders, const char *path) {
    char *copy = strdup(path);
    if (copy == NULL) {
        return NULL;
    }

    LIBMTP_folder_t *level = folders;
    LIBMTP_folder_t *current = NULL;
    char *part = strtok(copy, "/");
    while (part != NULL) {
        current = find_child(level, part);
        if (current == NULL) {
            free(copy);
            return NULL;
        }
        level = current->child;
        part = strtok(NULL, "/");
    }

    free(copy);
    return current;
}

static int is_numeric(const char *text) {
    if (text == NULL || *text == '\0') {
        return 0;
    }
    for (const char *cursor = text; *cursor != '\0'; cursor++) {
        if (*cursor < '0' || *cursor > '9') {
            return 0;
        }
    }
    return 1;
}

static uint32_t find_existing_file(LIBMTP_mtpdevice_t *device, uint32_t folder_id, const char *name) {
    LIBMTP_file_t *files = LIBMTP_Get_Filelisting(device);
    uint32_t item_id = 0;
    for (LIBMTP_file_t *file = files; file != NULL; file = file->next) {
        if (file->parent_id == folder_id && file->filename != NULL && strcmp(file->filename, name) == 0) {
            item_id = file->item_id;
            break;
        }
    }
    if (files != NULL) {
        LIBMTP_destroy_file_t(files);
    }
    return item_id;
}

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) {
        fprintf(stderr, "Usage: %s <local-file> <remote-name> <folder-id-or-path> [--replace]\n", argv[0]);
        return 2;
    }

    const char *local_path = argv[1];
    const char *remote_name = argv[2];
    const char *folder_target = argv[3];
    int replace = argc == 5 && strcmp(argv[4], "--replace") == 0;
    if (argc == 5 && !replace) {
        fprintf(stderr, "Unknown option: %s\n", argv[4]);
        return 2;
    }

    struct stat st;
    if (stat(local_path, &st) != 0) {
        perror("stat");
        return 2;
    }

    LIBMTP_Init();
    LIBMTP_mtpdevice_t *device = LIBMTP_Get_First_Device();
    if (device == NULL) {
        fprintf(stderr, "No MTP device found.\n");
        return 1;
    }

    LIBMTP_folder_t *folders = LIBMTP_Get_Folder_List(device);
    LIBMTP_folder_t *folder = is_numeric(folder_target)
        ? LIBMTP_Find_Folder(folders, (uint32_t) strtoul(folder_target, NULL, 10))
        : find_folder_path(folders, folder_target);
    if (folder == NULL) {
        fprintf(stderr, "Folder %s not found.\n", folder_target);
        LIBMTP_Release_Device(device);
        return 1;
    }
    uint32_t folder_id = folder->folder_id;

    uint32_t storage_id = folder->storage_id;
    if (storage_id == 0) {
        storage_id = first_storage_id(device);
    }
    if (storage_id == 0) {
        fprintf(stderr, "Could not resolve storage id.\n");
        LIBMTP_Release_Device(device);
        return 1;
    }

    uint32_t existing_id = find_existing_file(device, folder_id, remote_name);
    if (existing_id != 0 && !replace) {
        fprintf(stderr, "%s already exists in folder %u as object id %u. Use --replace to overwrite it.\n", remote_name, folder_id, existing_id);
        LIBMTP_Release_Device(device);
        return 3;
    }
    if (existing_id != 0 && LIBMTP_Delete_Object(device, existing_id) != 0) {
        fprintf(stderr, "Could not delete existing %s object id %u.\n", remote_name, existing_id);
        LIBMTP_Dump_Errorstack(device);
        LIBMTP_Clear_Errorstack(device);
        LIBMTP_Release_Device(device);
        return 1;
    }

    LIBMTP_file_t *file = LIBMTP_new_file_t();
    file->filename = strdup(remote_name);
    file->filesize = (uint64_t) st.st_size;
    file->parent_id = folder_id;
    file->storage_id = storage_id;
    file->modificationdate = st.st_mtime;
    file->filetype = LIBMTP_FILETYPE_UNKNOWN;

    int result = LIBMTP_Send_File_From_File(device, local_path, file, NULL, NULL);
    if (result != 0) {
        LIBMTP_Dump_Errorstack(device);
        LIBMTP_Clear_Errorstack(device);
        LIBMTP_destroy_file_t(file);
        LIBMTP_Release_Device(device);
        return 1;
    }

    printf("Sent %s to folder %u as %s (object id %u).\n", local_path, folder_id, remote_name, file->item_id);
    LIBMTP_destroy_file_t(file);
    LIBMTP_Release_Device(device);
    return 0;
}
