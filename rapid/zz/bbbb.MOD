module bbbb
CONST num VAL32_MIN := -2147483648;
CONST num VAL32_MAX :=  2147483647;
CONST num PORT := 1400;
CONST string IP := "192.168.0.203";
CONST num B24 := 16777216;   ! 0x1000000
CONST num B16 := 65536;      ! 0x10000
CONST num B08 := 256;        ! 0x100
CONST num B00 := 256;
var socketdev s1;
var byte cmd_buf{8};
var num num_buf;
var bool ol;
var num u32;

var num status{3};
var num order;
var intnum xx1;
var num aa;






proc aaaa()
mho;
fsj 0, 1;
plc_send 10;
fsj 1, 1;
while TRUE do
for i from 16 to 18 do
ssj i,order;
if order <> 0 then
fsj i,order-1;
order := i-15;
goto r4;
endif
endfor
r4:
plc_send order;
plc_send 7;
while TRUE do
plc_rec 1;
if status{1} = 1 then
goto r1;
endif
endwhile
r1:

run_plc ql,3,1,4,1,0,50,100;
mho;
movel sj,v2000,fine,tool0;
wt 1;
mho;
run fl,3,0,0.5,0,0,100;

while TRUE do
plc_rec 2;
if status{2} = 1 then
goto r5;
endif
endwhile
r5:

for i from 1 to 2 do
run lsk,2,1,0.5,0,0,100;
runb ls{i},1,1,i,0,0,100;
endfor
plc_send 5;

run qwl,3,1,0.5,0,0,200;
mho;
run fwl,3,0,0.5,0,0,100;
plc_send 7;

mho;

fsj 4,0;

endwhile
endproc

trap ixx1
fsj 5,1;
while true do
ssj 5,aa;
if aa = 0 goto r3;
endwhile
r3:
endtrap

proc zz1()
idelete xx1;
connect xx1 with ixx1;
isignaldi a3,1,xx1;
endproc

proc plc_rec(num x)
if a1 = 1 then
status{1}:=1;
else
status{1}:=0;
endif
if a2 = 1 then
status{2}:=1;
else
status{2}:=0;
endif
if a3 = 1 then
status{3}:=1;
else
status{3}:=0;
endif
endproc

proc plc_send(num x)
test x
case 1:set ddd;
case 2:set bdd;
case 3:set cdd;
case 4:set bygb;
case 5:set lsdw;
case 6:set bywl;
case 7:set qdxh;
case 8:set jt;
endtest
wt 2;
test x
case 1:reset ddd;
case 2:reset bdd;
case 3:reset cdd;
case 4:reset bygb;
case 5:reset lsdw;
case 6:reset bywl;
case 7:reset qdxh;
case 8:reset jt;
endtest
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

proc run(robtarget d, num a, num b, num c, num x, num y, num z)
movel offs(d,x,y,z),v2000,z10,tool0;
movel offs(d,0,0,0),v200,fine,tool0;
if b=1 then
test a
case 1:set dls;
case 2:set vc1;
case 3:set vc2;
endtest
else
test a
case 1:reset dls;
case 2:reset vc1;
case 3:reset vc2;
endtest
endif
wt c;
movel offs(d,x,y,z),v2000,z10,tool0;
endproc

proc run_plc(robtarget d, num a, num b, num c, num e, num x, num y, num z)
movel offs(d,0,0,z),v2000,z10,tool0;
movel offs(d,0,0,0),v200,fine,tool0;
if b=1 then
test a
case 1:set dls;
case 2:set vc1;
case 3:set vc2;
endtest
else
test a
case 1:reset dls;
case 2:reset vc1;
case 3:reset vc2;
endtest
endif
plc_send c;
while TRUE do
plc_rec e;
if status{e} = 1 then
goto r2;
endif
endwhile
r2:
movel offs(d,x,y,z),v2000,z10,tool0;
endproc

proc runb(robtarget d, num a, num b, num c, num x, num y, num z)
movel offs(d,x,y,z),v2000,z10,tool0;
movel offs(d,0,0,0),v200,fine,tool0;
if b=1 then
test a
case 1:set dls;
case 2:set vc1;
case 3:set vc2;
endtest
else
test a
case 1:reset dls;
case 2:reset vc1;
case 3:reset vc2;
endtest
endif
dls1 ls{c}, -12;
movel offs(d,x,y,z),v2000,z10,tool0;
endproc

proc dls1(robtarget d, num x)
set dls;
movel offs(d,0,0,x),v5,fine,tool0;
reset dls;
reset vc1;
endproc

proc mho()
movej home,v2000,z10,tool0;
endproc

proc wt(num x)
waittime x;
endproc

endmodule