// Exact radix-4 modified Booth group scheduler, with bitmap/counter controls.
module dot_engine #(
 parameter W=8,N=4,MODE=3,MAGNITUDE=0,O=2*W+$clog2(N)+1,
 D=(W+1)/2,P=(D>1?$clog2(D):1)
)(input wire clk,rst,in_valid,output wire in_ready,
 input wire [N*W-1:0] in_x,in_w,input wire [7:0] in_tag,
 output reg out_valid,input wire out_ready,
 output reg signed [O-1:0] out_sum,output reg [7:0] out_tag);
 reg busy;reg [N*W-1:0] ws;
 reg [N*D*3-1:0] ds;reg [D-1:0] todo;
 reg [P-1:0] current,last;
 reg signed [O-1:0] acc;reg [7:0] tag;
 assign in_ready=!busy&&(!out_valid||out_ready);
 integer i,j,low,high,plane;
 reg found;reg [2:0] triplet;reg signed [2:0] digit,coefficient;
 reg [N*D*3-1:0] encoded;reg [D-1:0] union_digits,next_mask;
 reg signed [O-1:0] extended,term,partial,total;
 function get_bit(input [W-1:0] x,input integer pos);
  begin
   if(pos<0)get_bit=0;
   else if(pos>=W)get_bit=x[W-1];
   else get_bit=x[pos];
  end
 endfunction
 always @*begin
  encoded=0;union_digits=0;triplet=0;digit=0;
  for(i=0;i<N;i=i+1)begin
   for(j=0;j<D;j=j+1)begin
    triplet={get_bit(in_x[i*W+:W],2*j+1),get_bit(in_x[i*W+:W],2*j),get_bit(in_x[i*W+:W],2*j-1)};
    case(triplet)
     3'b001,3'b010:digit=3'sd1;
     3'b011:digit=3'sd2;
     3'b100:digit=-3'sd2;
     3'b101,3'b110:digit=-3'sd1;
     default:digit=0;
    endcase
    encoded[(i*D+j)*3+:3]=digit;
    if(in_w[i*W+:W]!=0&&digit!=0)union_digits[j]=1;
   end
  end
  low=D-1;high=0;
  for(j=0;j<D;j=j+1)if(union_digits[j])begin if(j<low)low=j;high=j;end
  plane=current;found=0;
  if(MODE==3)begin
   plane=0;
   for(j=0;j<D;j=j+1)if(todo[j]&&!found)begin plane=j;found=1;end
  end
  next_mask=todo;next_mask[plane]=0;
  partial=0;extended=0;term=0;coefficient=0;
  for(i=0;i<N;i=i+1)begin
   extended=$signed(ws[i*W+:W]);coefficient=$signed(ds[(i*D+plane)*3+:3]);
   case(coefficient)
    3'sd1:term=extended;
    -3'sd1:term=-extended;
    3'sd2:term=extended<<<1;
    -3'sd2:term=-(extended<<<1);
    default:term=0;
   endcase
   partial=partial+term;
  end
  total=acc+(partial<<<(2*plane));
 end
 always @(posedge clk)begin
  if(rst)begin
   busy<=0;out_valid<=0;out_sum<=0;out_tag<=0;
   ws<=0;ds<=0;todo<=0;current<=0;last<=0;acc<=0;tag<=0;
  end else begin
   if(out_valid&&out_ready)out_valid<=0;
   if(in_valid&&in_ready)begin
    ws<=in_w;ds<=encoded;todo<=union_digits;current<=low;last<=high;acc<=0;tag<=in_tag;
    if(union_digits==0)begin out_sum<=0;out_tag<=in_tag;out_valid<=1;end
    else busy<=1;
   end
   if(busy)begin
    acc<=total;todo<=next_mask;current<=current+1'b1;
    if((MODE==3&&next_mask==0)||(MODE==5&&current==last))begin
     busy<=0;out_sum<=total;out_tag<=tag;out_valid<=1;
    end
   end
  end
 end
endmodule
