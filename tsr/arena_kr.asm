; Arena Korean text renderer TSR prototype
; NASM: nasm -f bin arena_kr.asm -o ARENAKR.COM

bits 16
cpu 386
org 0x100

%define API_WIDTH       0
%define API_DRAW        1
%define API_LINE_HEIGHT 2
%define API_SIGNATURE   0xFFFF
%define SIGNATURE       0x4B52          ; "KR"

%define ARENA_FONT_PTR  0xB034
%define ARENA_SCANLINES 0xA6A0
%define ARENA_SCREEN    0xA900
%define ARENA_COLOR     0x9288

%define BANK_PAGES      22
%define EMS_PAGES       66
%define EMS_PHYS_PAGE   3
%define EMS_PAGE_WORDS  0x400           ; 16 KiB in paragraphs
%define EMS_PAGE_BYTES  0x4000
%define LAST_PAGE_BYTES 0x3480          ; 357,504 - (21 * 16 KiB)
%define H9_WIDTH        10               ; 9 native pixels + 1 spacing column
%define H9_HEIGHT       9
%define H9_LINE         11
%define H12_WIDTH       12               ; Mulmaru's native 12px full-width cell
%define H12_HEIGHT      12
%define H12_LINE        14
%define H16_WIDTH       17               ; 16 native pixels + 1 spacing column
%define H16_HEIGHT      16
%define H16_LINE        18
%define GLYPH_SHIFT     5                ; 32 bytes per glyph
%define GLYPH_PAGE_BITS 9                ; 512 glyphs per EMS page

    jmp install

old_int60      dd 0
ems_handle     dw 0
ems_frame      dw 0

draw_x         dw 0
draw_y         dw 0
text_offset    dw 0
cursor_offset  dw 0
font_offset    dw 0
font_segment   dw 0
glyph_page     dw 0
glyph_offset   dw 0
glyph_index    dw 0
glyph_rows     db 0
glyph_width    db 0
draw_color     db 0
line_has_hangul db 0
active_glyph_width db H9_WIDTH
active_glyph_height db H9_HEIGHT
active_line_advance db H9_LINE
active_bank_page dw 0
glyph_buffer   times 16 dw 0        ; one fixed 32-byte Hangul glyph
move_region:
    dd 32                            ; bytes
    db 1                             ; source: expanded memory
move_src_handle dw 0
move_src_offset dw 0
move_src_page   dw 0
    db 0                             ; destination: conventional memory
    dw 0                             ; destination handle (unused)
    dw glyph_buffer
move_dest_segment dw 0

; Arena keeps its EMS machinery active while an FLC subtitle callback runs.
; Keep every H9 syllable used by staged runtime subtitles resident so drawing
; VISION.FLC, CHAOSVSN.FLC, and later scenes never calls the EMS manager.
%include "vision_h9_cache.inc"

resident_signature dw SIGNATURE

; API contract from patched ACD.EXE:
;   DX=0: DS:SI text, ES=Arena data segment, return AX=pixel width
;   DX=1: AX=x, BX=y, DS:SI text, ES=Arena data segment,
;         return SI immediately after the consumed NUL
;   DX=2: AL=original font height, DS:SI line, return AX=line advance
int60_handler:
    cmp dx, API_SIGNATURE
    je .signature
    cmp dx, API_WIDTH
    je width_handler
    cmp dx, API_DRAW
    je draw_handler
    cmp dx, API_LINE_HEIGHT
    je line_height_handler
    jmp far [cs:old_int60]
.signature:
    mov ax, SIGNATURE
    iret

width_handler:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    push fs
    push gs

    mov ax, es
    mov gs, ax                       ; GS = Arena data segment
    les di, [gs:ARENA_FONT_PTR]
    mov al, [es:di]
    call select_font_metrics
    xor bp, bp                       ; accumulated width

.next:
    lodsb
    test al, al
    jz .done
    test al, 0x80
    jnz .hangul
    cmp al, 0x20
    jb .next
    je .space
    cmp al, 0x7F
    ja .next
    sub al, 0x20
    xor ah, ah
    mov bx, ax
    mov al, [es:di+bx]
    xor ah, ah
    add bp, ax
    jmp .next

.space:
    mov al, [es:di+1]
    xor ah, ah
    inc ax
    add bp, ax
    jmp .next

.hangul:
    cmp al, 0xD7
    ja .next
    mov al, [si]
    test al, 0x80
    jz .next
    inc si
    xor ah, ah
    mov al, [cs:active_glyph_width]
    add bp, ax
    jmp .next

.done:
    mov ax, bp
    pop gs
    pop fs
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    iret

; Preserve the original line advance for ASCII-only lines. A line containing
; a valid AKC pair receives at least 11 scanlines so the native 9px Hangul
; bitmap never overlaps the following line.
line_height_handler:
    push bx
    push si
    mov bl, al                       ; original Arena font height
    call select_font_metrics

.scan:
    lodsb
    test al, al
    jz .original
    cmp al, 0x09                    ; color control + argument
    je .skip_argument
    cmp al, 0x0C                    ; font control + argument
    je .skip_argument
    test al, 0x80
    jz .scan
    cmp al, 0xD7
    ja .scan
    mov al, [si]
    test al, 0x80
    jz .scan

    xor ah, ah
    mov al, [cs:active_line_advance]
    jmp .done

.skip_argument:
    cmp byte [si], 0
    je .original
    inc si
    jmp .scan

.original:
    mov al, bl
    xor ah, ah
    inc ax

.done:
    pop si
    pop bx
    iret

; Select a native Hangul bank from the active English font height in AL.
; Question text uses FONT_B (6px), and therefore remains on the approved H9
; geometry. No bitmap is scaled at runtime.
select_font_metrics:
    cmp al, 9
    ja .maybe_h12
    mov byte [cs:active_glyph_width], H9_WIDTH
    mov byte [cs:active_glyph_height], H9_HEIGHT
    mov byte [cs:active_line_advance], H9_LINE
    mov word [cs:active_bank_page], 0
    ret
.maybe_h12:
    cmp al, 12
    ja .h16
    mov byte [cs:active_glyph_width], H12_WIDTH
    mov byte [cs:active_glyph_height], H12_HEIGHT
    mov byte [cs:active_line_advance], H12_LINE
    mov word [cs:active_bank_page], BANK_PAGES
    ret
.h16:
    mov byte [cs:active_glyph_width], H16_WIDTH
    mov byte [cs:active_glyph_height], H16_HEIGHT
    mov byte [cs:active_line_advance], H16_LINE
    mov word [cs:active_bank_page], BANK_PAGES * 2
    ret

draw_handler:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    push fs
    push gs

    mov [cs:draw_x], ax
    mov [cs:draw_y], bx
    mov [cs:text_offset], si
    mov ax, ds
    mov fs, ax                       ; FS = text segment
    mov ax, es
    mov gs, ax                       ; GS = Arena data segment

    ; Mixed lines use the Hangul cell as their vertical line box. Detect an
    ; AKC pair once so shorter ASCII glyphs can be bottom-aligned inside it.
    mov byte [cs:line_has_hangul], 0
    mov di, si
.scan_line:
    mov al, [fs:di]
    inc di
    test al, al
    jz .scan_done
    cmp al, 0x09
    je .scan_skip_argument
    cmp al, 0x0C
    je .scan_skip_argument
    test al, 0x80
    jz .scan_line
    cmp al, 0xD7
    ja .scan_line
    mov al, [fs:di]
    test al, 0x80
    jz .scan_line
    mov byte [cs:line_has_hangul], 1
    jmp .scan_done
.scan_skip_argument:
    cmp byte [fs:di], 0
    je .scan_done
    inc di
    jmp .scan_line
.scan_done:

    lds bp, [gs:ARENA_FONT_PTR]
    mov [cs:font_offset], bp
    mov ax, ds
    mov [cs:font_segment], ax
    mov al, [ds:bp]
    call select_font_metrics
    mov ax, [gs:ARENA_SCREEN]
    mov es, ax
    mov al, [gs:ARENA_COLOR]
    mov [cs:draw_color], al

    ; Arena does not always use y*320 for the active draw surface. During
    ; FLC playback its scanline table maps subtitle rows into the current
    ; video layout. Match the original renderer: table[y] + x.
    mov bx, [cs:draw_y]
    shl bx, 1
    mov ax, [gs:ARENA_SCANLINES+bx]
    add ax, [cs:draw_x]
    mov [cs:cursor_offset], ax

.next_char:
    mov si, [cs:text_offset]
    mov al, [fs:si]
    inc si
    mov [cs:text_offset], si
    test al, al
    jz .done
    test al, 0x80
    jnz .hangul
    cmp al, 0x20
    jb .next_char
    je .space
    cmp al, 0x7F
    ja .next_char

    ; ASCII glyph index is character - 33. Width table index is character - 32.
    sub al, 0x21
    xor ah, ah
    mov bx, ax                      ; BX = glyph index
    mov si, [cs:font_offset]
    add si, bx
    mov dl, [ds:si+1]
    mov [cs:glyph_width], dl
    mov si, [cs:font_offset]
    mov dl, [ds:si]
    mov [cs:glyph_rows], dl
    mov al, bl
    mul dl                          ; AX = glyph index * height
    shl ax, 1
    add ax, [cs:font_offset]
    add ax, 0x5F
    mov si, ax
    cmp byte [cs:line_has_hangul], 1
    jne .draw_ascii
    mov al, [cs:active_glyph_height]
    sub al, [cs:glyph_rows]
    jbe .draw_ascii
    xor ah, ah
    mov dx, 320
    mul dx
    add [cs:cursor_offset], ax
    call draw_bitmap16
    sub [cs:cursor_offset], ax
    jmp .next_char
.draw_ascii:
    call draw_bitmap16
    jmp .next_char

.space:
    mov si, [cs:font_offset]
    mov al, [ds:si+1]
    xor ah, ah
    inc ax
    add [cs:cursor_offset], ax
    jmp .next_char

.hangul:
    cmp al, 0xD7
    ja .next_char
    sub al, 0x80
    xor ah, ah
    mov bx, ax
    shl bx, 7
    mov si, [cs:text_offset]
    mov al, [fs:si]
    test al, 0x80
    jz .next_char
    inc si
    mov [cs:text_offset], si
    sub al, 0x80
    xor ah, ah
    add bx, ax                      ; BX = Hangul syllable index
    cmp bx, 11171
    ja .next_char
    mov [cs:glyph_index], bx

    mov ax, bx
    mov cl, GLYPH_PAGE_BITS
    shr ax, cl
    mov [cs:glyph_page], ax
    add ax, [cs:active_bank_page]
    mov [cs:glyph_page], ax
    and bx, 0x01FF
    mov cl, GLYPH_SHIFT
    shl bx, cl
    mov [cs:glyph_offset], bx

    mov al, [cs:active_glyph_height]
    mov [cs:glyph_rows], al
    mov al, [cs:active_glyph_width]
    mov [cs:glyph_width], al

    ; Runtime FLC subtitles use the 9px bank. Their translated syllables are
    ; cached in resident conventional memory because EMS calls made from an
    ; FLC subtitle callback do not complete reliably. A binary search keeps
    ; the per-glyph cost small; other H9 text falls back to the general path.
    cmp byte [cs:active_glyph_height], H9_HEIGHT
    jne .hangul_from_ems
    xor ax, ax                      ; low index, inclusive
    mov dx, VISION_H9_CACHE_COUNT  ; high index, exclusive
.vision_cache_search:
    cmp ax, dx
    jae .hangul_from_ems
    mov di, ax
    add di, dx
    shr di, 1                      ; DI = midpoint
    mov si, di
    imul si, VISION_H9_CACHE_ENTRY_BYTES
    add si, vision_h9_cache
    mov bp, [cs:glyph_index]
    cmp bp, [cs:si]
    jb .vision_cache_lower
    ja .vision_cache_higher
    add si, 2                      ; skip cached Unicode syllable index
    push cs
    pop ds
    call draw_bitmap16
    mov ax, [cs:font_segment]
    mov ds, ax
    jmp .next_char
.vision_cache_lower:
    mov dx, di
    jmp .vision_cache_search
.vision_cache_higher:
    lea ax, [di+1]
    jmp .vision_cache_search

.hangul_from_ems:
    ; EMS 4.0 move-region service copies 32 bytes straight from the logical
    ; font page into resident conventional memory. It never remaps any of the
    ; four physical EMS pages currently used by Arena's FLC framebuffer.
    mov ax, [cs:ems_handle]
    mov [cs:move_src_handle], ax
    mov ax, [cs:glyph_offset]
    mov [cs:move_src_offset], ax
    mov ax, [cs:glyph_page]
    mov [cs:move_src_page], ax
    mov ax, cs
    mov [cs:move_dest_segment], ax
    push cs
    pop ds
    mov si, move_region
    mov ax, 0x5700                  ; move expanded -> conventional memory
    int 0x67
    test ah, ah
    jnz .hangul_move_failed

    mov si, glyph_buffer
    call draw_bitmap16
    mov ax, [cs:font_segment]
    mov ds, ax
    jmp .next_char

.hangul_move_failed:
    mov ax, [cs:font_segment]
    mov ds, ax
    jmp .hangul_advance

.hangul_advance:
    xor ah, ah
    mov al, [cs:active_glyph_width]
    add [cs:cursor_offset], ax
    jmp .next_char

.done:
.restore_registers:
    pop gs
    pop fs
    pop es
    pop ds
    pop bp
    pop di
    add sp, 2                       ; discard saved input SI
    pop dx
    pop cx
    pop bx
    pop ax
    mov si, [cs:text_offset]        ; match original 9E0A side effect
    iret

; Draw glyph_rows little-endian 16-bit rows from DS:SI into ES framebuffer.
; Uses project-global cursor, color and width; preserves all caller registers.
draw_bitmap16:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov di, [cs:cursor_offset]
    xor bh, bh
    mov bl, [cs:glyph_rows]
    xor ch, ch

.row:
    lodsw
    mov dx, ax
    mov cl, [cs:glyph_width]
.pixel:
    shl dx, 1
    jnc .transparent
    mov al, [cs:draw_color]
    mov [es:di], al
.transparent:
    inc di
    loop .pixel
    mov ax, 320
    xor dh, dh
    mov dl, [cs:glyph_width]
    sub ax, dx
    add di, ax
    dec bx
    jnz .row

    xor ah, ah
    mov al, [cs:glyph_width]
    add [cs:cursor_offset], ax
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

resident_end:

font_filename9  db 'HANGUL.FNT', 0
font_filename12 db 'HANGUL12.FNT', 0
font_filename16 db 'HANGUL16.FNT', 0
msg_installed db 'Arena Korean renderer installed.', 13, 10, '$'
msg_already   db 'Arena Korean renderer already installed.', 13, 10, '$'
msg_no_font   db 'HANGUL.FNT/HANGUL12.FNT/HANGUL16.FNT not found.', 13, 10, '$'
msg_no_ems    db 'EMS allocation/loading failed.', 13, 10, '$'
file_handle   dw 0
page_map_was_saved db 0

print_dollar_string:
    mov ah, 0x09
    int 0x21
    ret

close_font:
    mov bx, [file_handle]
    mov ah, 0x3E
    int 0x21
    ret

; Load one 22-page raw bank. DX=filename, BP=first logical EMS page.
; Returns CF set for either an open/read/map failure.
load_font_bank:
    mov ax, 0x3D00
    int 0x21
    jc .failed
    mov [file_handle], ax
    mov di, bp
    add di, BANK_PAGES
.load_page:
    mov bx, bp
    mov dx, [ems_handle]
    mov ax, 0x4400 + EMS_PHYS_PAGE
    int 0x67
    test ah, ah
    jnz .failed_close
    push ds
    mov ax, [cs:ems_frame]
    add ax, EMS_PHYS_PAGE * EMS_PAGE_WORDS
    mov ds, ax
    ; The raw bank occupies 21 complete pages plus 13,440 bytes. Clear the
    ; mapped page first so the unused tail of the final page is deterministic.
    xor bx, bx
    xor ax, ax
    mov cx, EMS_PAGE_BYTES / 2
.clear_page:
    mov [bx], ax
    add bx, 2
    loop .clear_page
    xor dx, dx
    mov cx, EMS_PAGE_BYTES
    mov bx, [cs:file_handle]
    mov ah, 0x3F
    int 0x21
    pop ds
    jc .failed_close
    mov bx, di
    dec bx
    cmp bp, bx
    je .check_last_page
    cmp ax, EMS_PAGE_BYTES
    jne .failed_close
    jmp .page_ok
.check_last_page:
    cmp ax, LAST_PAGE_BYTES
    jne .failed_close
.page_ok:
    inc bp
    cmp bp, di
    jb .load_page
    call close_font
    clc
    ret
.failed_close:
    call close_font
.failed:
    stc
    ret

release_ems:
    mov dx, [ems_handle]
    test dx, dx
    jz .done
    mov ah, 0x45
    int 0x67
.done:
    ret

install:
    push cs
    pop ds

    ; Inspect the vector without executing an unknown previous INT 60h handler.
    mov ax, 0x3560
    int 0x21
    mov [old_int60], bx
    mov [old_int60+2], es
    cmp bx, 2
    jb .open_font
    cmp word [es:bx-2], SIGNATURE
    jne .open_font
    mov dx, msg_already
    call print_dollar_string
    mov ax, 0x4C00
    int 0x21

.open_font:
    mov ah, 0x40                    ; EMS status
    int 0x67
    test ah, ah
    jnz .ems_error
    mov ah, 0x41                    ; EMS page frame segment
    int 0x67
    test ah, ah
    jnz .ems_error
    mov [ems_frame], bx
    mov bx, EMS_PAGES
    mov ah, 0x43                    ; allocate EMS pages
    int 0x67
    test ah, ah
    jnz .ems_error
    mov [ems_handle], dx

    mov dx, [ems_handle]
    mov ah, 0x47                    ; save pre-existing page map
    int 0x67
    test ah, ah
    jnz .ems_error_release
    mov byte [page_map_was_saved], 1

    xor bp, bp
    mov dx, font_filename9
    call load_font_bank
    jc .font_error_restore
    mov dx, font_filename12
    call load_font_bank
    jc .font_error_restore
    mov dx, font_filename16
    call load_font_bank
    jc .font_error_restore

    mov dx, [ems_handle]
    mov ah, 0x48
    int 0x67
    mov byte [page_map_was_saved], 0

    ; Install our handler; the previous vector was saved before allocation.
    push ds
    push cs
    pop ds
    mov dx, int60_handler
    mov ax, 0x2560
    int 0x21
    pop ds

    mov dx, msg_installed
    call print_dollar_string
    ; Paragraphs measured from the PSP, including the COM load offset 0x100.
    mov dx, (resident_end - $$ + 0x10F) / 16
    mov ax, 0x3100
    int 0x21

.font_error:
    mov dx, msg_no_font
    call print_dollar_string
    mov ax, 0x4C01
    int 0x21

.font_error_restore:
    cmp byte [page_map_was_saved], 1
    jne .font_error_release
    mov dx, [ems_handle]
    mov ah, 0x48
    int 0x67
.font_error_release:
    call release_ems
    mov dx, msg_no_font
    call print_dollar_string
    mov ax, 0x4C01
    int 0x21

.ems_error_restore:
    cmp byte [page_map_was_saved], 1
    jne .ems_error_release
    mov dx, [ems_handle]
    mov ah, 0x48
    int 0x67
.ems_error_release:
    call release_ems
.ems_error:
    mov dx, msg_no_ems
    call print_dollar_string
    mov ax, 0x4C02
    int 0x21
