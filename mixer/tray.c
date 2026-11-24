#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

static NOTIFYICONDATAW icon;
static UINT taskbar_created;
static const UINT notify = WM_APP + 1;
static WCHAR folder[MAX_PATH], player[MAX_PATH], args[MAX_PATH+8];

static void register_icon(HWND w) {
    icon.cbSize = sizeof(icon);
    icon.hWnd = w;
    icon.uID = 1;
    icon.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    icon.uCallbackMessage = notify;
    wcscpy(icon.szTip, L"SplitDesk · Stereo Mixer");
    Shell_NotifyIconW(NIM_ADD, &icon);
}

static void open_mixer(HWND w) {
    HWND found = FindWindowW(NULL, L"SplitDesk · Stereo Mixer");
    if (found) {
        ShowWindow(found, IsZoomed(found) ? SW_SHOWMAXIMIZED : SW_RESTORE);
        SetForegroundWindow(found);
    } else if ((INT_PTR)ShellExecuteW(w, L"open", player, args, folder, SW_SHOWNORMAL) <= 32) {
        MessageBoxW(w, L"Could not open the mixer. Check the installation files.", L"SplitDesk", MB_ICONERROR);
    }
}

static LRESULT CALLBACK events(HWND w, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == taskbar_created) {
        register_icon(w);
        return 0;
    }
    if (msg == WM_APP + 2) { open_mixer(w); return 0; }
    if (msg == notify) {
        if (lp == WM_LBUTTONUP) open_mixer(w);
        if (lp == WM_RBUTTONUP) {
            POINT pt;
            GetCursorPos(&pt);
            HMENU menu = CreatePopupMenu();
            AppendMenuW(menu, MF_STRING, 1, L"Open Mixer");
            AppendMenuW(menu, MF_STRING, 2, L"Quit Tray");
            SetForegroundWindow(w);
            int cmd = TrackPopupMenu(menu, TPM_RETURNCMD|TPM_RIGHTBUTTON, pt.x, pt.y, 0, w, NULL);
            DestroyMenu(menu);
            if (cmd == 1) open_mixer(w);
            if (cmd == 2) DestroyWindow(w);
            PostMessageW(w, WM_NULL, 0, 0);
        }
        return 0;
    }
    if (msg == WM_DESTROY) {
        Shell_NotifyIconW(NIM_DELETE, &icon);
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(w,msg,wp,lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show) {
    HANDLE mutex = CreateMutexW(NULL, FALSE, L"Local\\SplitDeskStereoTray");
    if (!mutex) return 1;
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        if (wcsstr(cmd, L"/open")) {
            HWND existing=NULL;
            for (int i=0; i<20 && !existing; i++) {
                existing=FindWindowW(L"SplitDeskTrayWindow", NULL);
                if (!existing) Sleep(25);
            }
            if (existing) {
                DWORD pid;
                GetWindowThreadProcessId(existing, &pid);
                AllowSetForegroundWindow(pid);
                PostMessageW(existing, WM_APP+2, 0, 0);
            }
        }
        return 0;
    }
    if (!GetModuleFileNameW(NULL,folder,MAX_PATH) || !wcsrchr(folder,L'\\')) return 1;
    *wcsrchr(folder,L'\\')=0;
    if (wcslen(folder) > MAX_PATH-40) return 1;
    swprintf(player, MAX_PATH, L"%ls\\..\\venv\\Scripts\\pythonw.exe", folder);
    swprintf(args, MAX_PATH+8, L"\"%ls\\..\\launch.py\"", folder);
    WCHAR ico[MAX_PATH];
    swprintf(ico, MAX_PATH,L"%ls\\walnut.ico",folder);
    icon.hIcon = (HICON)LoadImageW(NULL, ico, IMAGE_ICON, 0, 0, LR_LOADFROMFILE|LR_DEFAULTSIZE);
    if (!icon.hIcon) icon.hIcon = LoadIconW(NULL, IDI_APPLICATION);
    taskbar_created=RegisterWindowMessageW(L"TaskbarCreated");
    WNDCLASSW cls={0};
    cls.lpfnWndProc=events; cls.hInstance=inst; cls.lpszClassName=L"SplitDeskTrayWindow";
    if (!RegisterClassW(&cls)) return 1;
    HWND w=CreateWindowExW(WS_EX_TOOLWINDOW,cls.lpszClassName,L"",WS_POPUP,0,0,0,0,NULL,NULL,inst,NULL);
    if (!w) return 1;
    register_icon(w);
    if (wcsstr(cmd, L"/open")) PostMessageW(w, WM_APP+2, 0, 0);
    MSG msg;
    while (GetMessageW(&msg,NULL,0,0)>0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    CloseHandle(mutex);
    return 0;
}
