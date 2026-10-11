module proof(input clk);
 parameter MODE=3;
 (* anyseq *) reg rst,iv,ready;
 (* anyseq *) reg signed [2:0] x,w;
 (* anyseq *) reg [7:0] tag;
 wire ir,ov;wire signed [6:0] value;wire [7:0] ot;
 dot_engine #(.W(3),.N(1),.MODE(MODE)) dut(clk,rst,iv,ir,x,w,tag,ov,ready,value,ot);
 reg pending=0;reg signed [6:0] reference=0;reg [7:0] expected_tag=0;
 always @(posedge clk) begin
  if(rst)pending<=0;
  else begin
   if(ov) begin assert(pending);assert(value==reference);assert(ot==expected_tag);end
   if(ov&&ready)pending<=0;
   if(iv&&ir)begin pending<=1;reference<=$signed(x)*$signed(w);expected_tag<=tag;end
  end
 end
endmodule
