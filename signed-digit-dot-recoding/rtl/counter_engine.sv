// Derived from weight-qualified-bitplane-dot at commit 394ce36c7677837dc95f7e8621eb4ba0313bb2bf.
// Magnitude recoding widens signed weights before conditional negation.
module dot_engine #(
 parameter W=8,N=4,MODE=5,MAGNITUDE=0,SW=W+MAGNITUDE,O=2*W+$clog2(N)+1,P=$clog2(W)
)(input wire clk,rst,in_valid,output wire in_ready,
 input wire [N*W-1:0] in_x,in_w,input wire [7:0] in_tag,
 output reg out_valid,input wire out_ready,
 output reg signed [O-1:0] out_sum,output reg [7:0] out_tag);
 reg busy;reg [N*W-1:0] xs;reg [N*SW-1:0] ws;
 reg [P-1:0] current,last;
 reg signed [O-1:0] acc;reg [7:0] tag;
 assign in_ready=!busy&&(!out_valid||out_ready);
 reg [N*W-1:0] normalized_x;reg [N*SW-1:0] normalized_w;
 reg signed [SW-1:0] signed_weight;
 integer i,b,low,high;reg [W-1:0] union_bits;
 reg signed [O-1:0] partial,extended,shifted,total;
 always @* begin
  for(i=0;i<N;i=i+1)begin
   normalized_x[i*W+:W]=(MAGNITUDE&&in_x[i*W+W-1])?((~in_x[i*W+:W])+1'b1):in_x[i*W+:W];
   signed_weight=$signed(in_w[i*W+:W]);
   normalized_w[i*SW+:SW]=(MAGNITUDE&&in_x[i*W+W-1])?-signed_weight:signed_weight;
  end
  union_bits=0;for(i=0;i<N;i=i+1)if(in_w[i*W+:W]!=0) union_bits=union_bits|normalized_x[i*W+:W];
  low=W-1;high=0;
  for(b=0;b<W;b=b+1)if(union_bits[b])begin if(b<low)low=b;high=b;end
  partial=0;
  for(i=0;i<N;i=i+1)begin extended=$signed(ws[i*SW+:SW]);if(xs[i*W+current])partial=partial+extended;end
  shifted=partial<<<current;
  if(!MAGNITUDE&&current==W-1)total=acc-shifted;else total=acc+shifted;
 end
 always @(posedge clk)begin
  if(rst)begin busy<=0;out_valid<=0;out_sum<=0;out_tag<=0;xs<=0;ws<=0;current<=0;last<=0;acc<=0;tag<=0;end
  else begin
   if(out_valid&&out_ready)out_valid<=0;
   if(in_valid&&in_ready)begin
    xs<=normalized_x;ws<=normalized_w;current<=low;last<=high;acc<=0;tag<=in_tag;
    if(union_bits==0)begin out_valid<=1;out_sum<=0;out_tag<=in_tag;end else busy<=1;
   end
   if(busy)begin
    acc<=total;
    if(current==last)begin busy<=0;out_valid<=1;out_sum<=total;out_tag<=tag;end
    else current<=current+1'b1;
   end
  end
 end
endmodule
