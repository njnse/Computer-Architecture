// Derived from weight-qualified-bitplane-dot at commit 394ce36c7677837dc95f7e8621eb4ba0313bb2bf.
// Magnitude recoding widens signed weights before conditional negation.
module dot_engine #(
 parameter W=8, N=4, MODE=3, MAGNITUDE=0,SW=W+MAGNITUDE, O=2*W+$clog2(N)+1
)(input wire clk,rst,in_valid,output wire in_ready,
 input wire [N*W-1:0] in_x,in_w,input wire [7:0] in_tag,
 output reg out_valid,input wire out_ready,
 output reg signed [O-1:0] out_sum,output reg [7:0] out_tag);
 reg busy;
 reg [N*W-1:0] xs;reg [N*SW-1:0] ws;
 reg [W-1:0] todo;
 reg signed [O-1:0] acc;
 reg [7:0] tag;
 wire take=in_valid&&in_ready;
 assign in_ready=!busy&&(!out_valid||out_ready);
 reg [N*W-1:0] normalized_x;reg [N*SW-1:0] normalized_w;
 reg signed [SW-1:0] signed_weight;
 integer i,b,plane,highest,lowest;
 reg found;
 reg [W-1:0] union_bits,start_mask,next_mask;
 reg signed [O-1:0] partial,shifted,total,parallel_sum,extended_weight;
 always @* begin
  for(i=0;i<N;i=i+1)begin
   normalized_x[i*W+:W]=(MAGNITUDE&&in_x[i*W+W-1])?((~in_x[i*W+:W])+1'b1):in_x[i*W+:W];
   signed_weight=$signed(in_w[i*W+:W]);
   normalized_w[i*SW+:SW]=(MAGNITUDE&&in_x[i*W+W-1])?-signed_weight:signed_weight;
  end
  union_bits=0;
  for(i=0;i<N;i=i+1) if(in_w[i*W+:W]!=0) union_bits=union_bits|normalized_x[i*W+:W];
  highest=-1;lowest=W;
  for(b=0;b<W;b=b+1) if(union_bits[b]) begin highest=b;if(b<lowest)lowest=b;end
  start_mask=0;
  for(b=0;b<W;b=b+1) begin
   if(MODE==1) start_mask[b]=1'b1;
   else if(MODE==2) start_mask[b]=(b<=highest);
   else if(MODE==4) start_mask[b]=(b>=lowest&&b<=highest);
   else start_mask[b]=union_bits[b];
  end
  plane=0;found=0;
  for(b=0;b<W;b=b+1) if(todo[b]&&!found) begin plane=b;found=1;end
  next_mask=todo;next_mask[plane]=0;
  partial=0;
  for(i=0;i<N;i=i+1) begin
   extended_weight=$signed(ws[i*SW+:SW]);
   if(xs[i*W+plane]) partial=partial+extended_weight;
  end
  shifted=partial<<<plane;
  if(!MAGNITUDE&&plane==W-1) total=acc-shifted;
  else total=acc+shifted;
  parallel_sum=0;
  for(i=0;i<N;i=i+1) parallel_sum=parallel_sum+($signed(in_x[i*W+:W])*$signed(in_w[i*W+:W]));
 end
 always @(posedge clk) begin
  if(rst) begin
   busy<=0;out_valid<=0;out_sum<=0;out_tag<=0;
   xs<=0;ws<=0;todo<=0;acc<=0;tag<=0;
  end else begin
   if(out_valid&&out_ready) out_valid<=0;
   if(take) begin
    if(MODE==0) begin out_sum<=parallel_sum;out_tag<=in_tag;out_valid<=1;end
    else begin
     xs<=normalized_x;ws<=normalized_w;todo<=start_mask;acc<=0;tag<=in_tag;
     if(start_mask==0) begin out_sum<=0;out_tag<=in_tag;out_valid<=1;end
     else busy<=1;
    end
   end
   if(busy && MODE!=0) begin
    acc<=total;todo<=next_mask;
    if(next_mask==0) begin busy<=0;out_sum<=total;out_tag<=tag;out_valid<=1;end
   end
  end
 end
endmodule
