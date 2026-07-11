; Arena Korean text renderer TSR prototype
; NASM: nasm -f bin arena_kr.asm -o ARENAKR.COM

bits 16
cpu 386
org 0x100

%define API_WIDTH       0
%define API_DRAW        1
%define API_SIGNATURE   0xFFFF
%define SIGNATURE       0x4B52          ; "KR"

%define ARENA_FONT_PTR  0xB034
%define ARENA_SCANLINES 0xA6A0
%define ARENA_SCREEN    0xA900
%define ARENA_COLOR     0x9288

%define EMS_PAGES       22
%define EMS_PHYS_PAGE   3
%define EMS_PAGE_WORDS  0x400           ; 16 KiB in paragraphs
%define EMS_PAGE_BYTES  0x4000
%define GLYPH_WIDTH     10               ; 9 pixels + 1 spacing column
%define SOURCE_GLYPH_HEIGHT 9            ; stored HANGUL.FNT bitmap height
%define MAX_GLYPH_HEIGHT    8            ; leave room for Arena's line pitch
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
glyph_rows     db 0
glyph_width    db 0
draw_color     db 0
map_saved      db 0
scale_row      db 0
scale_col      db 0
scale_bits     dw 0
scale_base     dw 0

resident_signature dw SIGNATURE

; API contract from patched ACD.EXE:
;   DX=0: DS:SI text, ES=Arena data segment, return AX=pixel width
;   DX=1: AX=x, BX=y, DS:SI text, ES=Arena data segment
int60_handler:
    cmp dx, API_SIGNATURE
    je .signature
    cmp dx, API_WIDTH
    je width_handler
    cmp dx, API_DRAW
    je draw_handler
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
    mov al, [es:di]                  ; fit Korean advance to active font height
    cmp al, MAX_GLYPH_HEIGHT
    jbe .hangul_width_ready
    mov al, MAX_GLYPH_HEIGHT
.hangul_width_ready:
    xor ah, ah
    inc ax                           ; one blank spacing column
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

    lds bp, [gs:ARENA_FONT_PTR]
    mov [cs:font_offset], bp
    mov ax, ds
    mov [cs:font_segment], ax
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

    mov byte [cs:map_saved], 0
    mov dx, [cs:ems_handle]
    mov ah, 0x47                    ; save complete EMS page map in handle
    int 0x67
    test ah, ah
    jnz .next_char
    mov byte [cs:map_saved], 1

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

    mov ax, bx
    mov cl, GLYPH_PAGE_BITS
    shr ax, cl
    mov [cs:glyph_page], ax
    and bx, 0x01FF
    mov cl, GLYPH_SHIFT
    shl bx, cl
    mov [cs:glyph_offset], bx

    cmp byte [cs:map_saved], 1
    jne .hangul_advance

    ; Small Arena fonts are only 5-8 pixels high. Scale the 9x9 Hangul
    ; bitmap down to the active font height so map notes and lists do not
    ; overlap vertically or horizontally.
    mov si, [cs:font_offset]
    mov al, [ds:si]
    cmp al, MAX_GLYPH_HEIGHT
    jbe .hangul_size_ready
    mov al, MAX_GLYPH_HEIGHT
.hangul_size_ready:
    mov [cs:glyph_rows], al
    inc al
    mov [cs:glyph_width], al

    mov bx, [cs:glyph_page]
    mov dx, [cs:ems_handle]
    mov ax, 0x4400 + EMS_PHYS_PAGE
    int 0x67
    test ah, ah
    jnz .hangul_advance

    mov ax, [cs:ems_frame]
    add ax, EMS_PHYS_PAGE * EMS_PAGE_WORDS
    mov ds, ax
    mov si, [cs:glyph_offset]
    call draw_hangul_scaled
    mov ax, [cs:font_segment]
    mov ds, ax
    jmp .next_char

.hangul_advance:
    mov si, [cs:font_offset]
    mov al, [ds:si]
    cmp al, MAX_GLYPH_HEIGHT
    jbe .hangul_advance_ready
    mov al, MAX_GLYPH_HEIGHT
.hangul_advance_ready:
    xor ah, ah
    inc ax
    add [cs:cursor_offset], ax
    jmp .next_char

.done:
    cmp byte [cs:map_saved], 1
    jne .restore_registers
    mov dx, [cs:ems_handle]
    mov ah, 0x48                    ; restore Arena's complete EMS page map
    int 0x67

.restore_registers:
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
    pop ax
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

; Nearest-neighbor scale of a 9x9 Hangul glyph to glyph_rows high and
; (glyph_width-1) visible pixels wide, followed by one spacing column.
draw_hangul_scaled:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov [cs:scale_base], si
    mov byte [cs:scale_row], 0
    mov di, [cs:cursor_offset]

.row:
    mov al, [cs:scale_row]
    mov bl, SOURCE_GLYPH_HEIGHT
    mul bl
    div byte [cs:glyph_rows]
    xor ah, ah
    shl ax, 1
    mov si, [cs:scale_base]
    add si, ax
    mov dx, [ds:si]
    mov [cs:scale_bits], dx
    mov byte [cs:scale_col], 0

.pixel:
    mov bl, [cs:glyph_width]
    dec bl
    cmp [cs:scale_col], bl
    jae .row_done
    mov al, [cs:scale_col]
    mov cl, GLYPH_WIDTH - 1
    mul cl
    div bl
    mov cl, al
    mov ax, 0x8000
    shr ax, cl
    test [cs:scale_bits], ax
    jz .transparent
    mov al, [cs:draw_color]
    mov [es:di], al
.transparent:
    inc di
    inc byte [cs:scale_col]
    jmp .pixel

.row_done:
    inc di                           ; spacing column
    mov ax, 320
    xor bh, bh
    mov bl, [cs:glyph_width]
    sub ax, bx
    add di, ax
    inc byte [cs:scale_row]
    mov al, [cs:scale_row]
    cmp al, [cs:glyph_rows]
    jb .row

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

font_filename db 'HANGUL.FNT', 0
msg_installed db 'Arena Korean renderer installed.', 13, 10, '$'
msg_already   db 'Arena Korean renderer already installed.', 13, 10, '$'
msg_no_font   db 'HANGUL.FNT not found.', 13, 10, '$'
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
    mov dx, font_filename
    mov ax, 0x3D00
    int 0x21
    jc .font_error
    mov [file_handle], ax

    mov ah, 0x40                    ; EMS status
    int 0x67
    test ah, ah
    jnz .ems_error_close
    mov ah, 0x41                    ; EMS page frame segment
    int 0x67
    test ah, ah
    jnz .ems_error_close
    mov [ems_frame], bx
    mov bx, EMS_PAGES
    mov ah, 0x43                    ; allocate EMS pages
    int 0x67
    test ah, ah
    jnz .ems_error_close
    mov [ems_handle], dx

    mov dx, [ems_handle]
    mov ah, 0x47                    ; save pre-existing page map
    int 0x67
    test ah, ah
    jnz .ems_error_release
    mov byte [page_map_was_saved], 1

    xor bp, bp
.load_page:
    mov bx, bp
    mov dx, [ems_handle]
    mov ax, 0x4400 + EMS_PHYS_PAGE
    int 0x67
    test ah, ah
    jnz .ems_error_restore

    push ds
    mov ax, [cs:ems_frame]
    add ax, EMS_PHYS_PAGE * EMS_PAGE_WORDS
    mov ds, ax
    xor dx, dx
    mov cx, EMS_PAGE_BYTES
    mov bx, [cs:file_handle]
    mov ah, 0x3F
    int 0x21
    pop ds
    jc .ems_error_restore
    inc bp
    cmp bp, EMS_PAGES
    jb .load_page

    mov dx, [ems_handle]
    mov ah, 0x48
    int 0x67
    mov byte [page_map_was_saved], 0
    call close_font

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

.ems_error_restore:
    cmp byte [page_map_was_saved], 1
    jne .ems_error_release
    mov dx, [ems_handle]
    mov ah, 0x48
    int 0x67
.ems_error_release:
    call release_ems
.ems_error_close:
    call close_font
    mov dx, msg_no_ems
    call print_dollar_string
    mov ax, 0x4C02
    int 0x21
