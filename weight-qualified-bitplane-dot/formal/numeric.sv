module proof(input clk);
 parameter MODE=3,MASK_WEIGHTS=1,W=3,N=2,O=2*W+$clog2(N)+1;
 (* anyseq *) reg rst,iv,ready;
 (* anyseq *) reg [N*W-1:0] x,w;
 (* anyseq *) reg [7:0] tag;
 wire ir,ov;wire signed [O-1:0] value;wire [7:0] ot;
 dot_engine #(.W(W),.N(N),.MODE(MODE),.MASK_WEIGHTS(MASK_WEIGHTS)) dut(clk,rst,iv,ir,x,w,tag,ov,ready,value,ot);
 reg pending=0;reg signed [O-1:0] reference=0;reg [7:0] expected_tag=0;
 reg held=0;reg signed [O-1:0] held_value=0;reg [7:0] held_tag=0;
 integer j;reg signed [O-1:0] math;
 always @*begin
  math=0;for(j=0;j<N;j=j+1)math=math+($signed(x[j*W+:W])*$signed(w[j*W+:W]));
 end
 always @(posedge clk)begin
  if(rst)begin pending<=0;held<=0;end
  else begin
   if(held)begin assert(ov);assert(value==held_value);assert(ot==held_tag);end
   if(ov&&!ready)assert(!ir);
   held<=ov&&!ready;held_value<=value;held_tag<=ot;
   if(ov)begin assert(pending);assert(value==reference);assert(ot==expected_tag);end
   if(ov&&ready)pending<=0;
   if(iv&&ir)begin pending<=1;reference<=math;expected_tag<=tag;end
  end
 end
endmodule
