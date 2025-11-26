module bbbb
CONST num VAL32_MIN := -2147483648;
CONST num VAL32_MAX :=  2147483647;
CONST num PORT := 1400;
CONST string IP := "192.168.0.3";
CONST num B24 := 16777216;   ! 0x1000000
CONST num B16 := 65536;      ! 0x10000
CONST num B08 := 256;        ! 0x100
CONST num B00 := 256;
var socketdev s1;
var byte cmd_buf{8};
var num num_buf;
var bool ol;
var num u32;

var num start;
var num order;
var num mdsl{3};






proc aaaa()
mho;
fsj 2, 1;
while TRUE do
while TRUE do
ssj 5, start;
if start<>0 goto r1;
waittime 0.5;
endwhile
r1:
if start = 1 then
ssj 19, order;
run qld,1,0.5,0,0,100;
mdsl{order}:=mdsl{order} + 1;
mho;
run mdd{order,mdsl{order}},2,0.5,0,0,100;
mho;
if mdsl{order} = 3 mdsl{order}:=0;
endif
fsj 5,0;
endwhile
fsj 2, 1;
endproc


proc fsj(num x, num y)
clear_buf;
SocketCreate s1;
SocketConnect s1, IP, PORT;
cmd_buf{1}:=80;
cmd_buf{2}:=x;
socketsend s1\data:=cmd_buf;
socketreceive s1\data:=cmd_buf;
clear_buf;
cmd_buf{1}:=82;
cmd_buf{2}:=x;
ol := I32_To_Bytes(y, cmd_buf{5},cmd_buf{6},cmd_buf{7},cmd_buf{8});
socketsend s1\data:=cmd_buf;
socketreceive s1\data:=cmd_buf;
clear_buf;
socketclose s1;
endproc

proc ssj(num x, INOUT num y)
clear_buf;
SocketCreate s1;
SocketConnect s1, IP, PORT;
cmd_buf{1}:=64;
cmd_buf{2}:=x;
socketsend s1\data:=cmd_buf;
socketreceive s1\data:=cmd_buf;
y := Bytes_To_I32(cmd_buf{5},cmd_buf{6},cmd_buf{7},cmd_buf{8});
clear_buf;
cmd_buf{1}:=66;
cmd_buf{2}:=x;
socketsend s1\data:=cmd_buf;
clear_buf;
socketclose s1;
endproc

proc clear_buf()
for i from 1 to 8 do
cmd_buf{i}:=0;
endfor
endproc

FUNC bool I32_To_Bytes(num value, INOUT byte b0, INOUT byte b1,
                                   INOUT byte b2, INOUT byte b3)
    IF value < VAL32_MIN OR value > VAL32_MAX THEN
        TPWrite "I32_To_Bytes: value out of range";
        RETURN FALSE;
    ENDIF

    u32 := value;
    IF value < 0 THEN
        u32 := value + 4294967296;
    ENDIF

    b1 := (TRUNC(u32) DIV B16) MOD B00;
    b2 := (TRUNC(u32) DIV B08) MOD B00;
    b3 := TRUNC(u32) MOD B00;
    RETURN TRUE;
ENDFUNC

FUNC num Bytes_To_I32(byte b0, byte b1, byte b2, byte b3)
    u32 := b0 * 16777216 + b1 * 65536 + b2 * 256 + b3;
    IF u32 >= 2147483648 THEN
        RETURN u32 - 4294967296;
    ELSE
        RETURN u32;
    ENDIF
ENDFUNC

proc run(robtarget d, num a, num c, num x, num y, num z)
movel offs(d,x,y,z),v2000,z10,tool0;
movel offs(d,0,0,0),v200,fine,tool0;
if a=1 then
set vc1;
else
reset vc1;
endif
wt c;
movel offs(d,x,y,z),v2000,z10,tool0;
endproc

proc mho()
movej home,v2000,z10,tool0;
endproc

proc wt(num x)
waittime x;
endproc

endmodule