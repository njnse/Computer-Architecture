// Handshake scoreboard adapted from the attributed predecessor; not UVM.
module check;
 parameter W=8,N=4,MODE=3,MAGNITUDE=0,O=2*W+$clog2(N)+1;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,iv=0,orr=0;wire ir,ov;
 reg [N*W-1:0] x,w;wire signed [O-1:0] sum;wire [7:0] tag;
 integer index=0;wire [7:0] itag=index;
`ifdef NETLIST
 dot_engine dut(clk,rst,iv,ir,x,w,itag,ov,orr,sum,tag);
`else
 dot_engine #(.W(W),.N(N),.MODE(MODE),.MAGNITUDE(MAGNITUDE)) dut(clk,rst,iv,ir,x,w,itag,ov,orr,sum,tag);
`endif
 reg [N*W-1:0] xv[0:100000],wv[0:100000];
 integer expected[0:100000],queued[0:100000],accepted_cycle[0:100000];
 integer count=0,head=0,tail=0,cycle=0,emitted=0,canceled=0,installs=0,outstalls=0,busyreset=0,outputreset=0;
 integer f,o,rc,seed=7,traffic=0,resets=0,j,oracle,a,b,latency,total_latency=0,max_latency=0;
 integer firstaccept=-1,lastaccept=-1,firstemit=-1,lastemit=-1,zero_groups=0,negative_groups=0, simultaneous=0;
 reg signed [O-1:0] held_sum;reg [7:0] held_tag;reg held=0;
 reg [31:0] rng;
 reg [W-1:0] ub,qb;reg neg;
 integer zero_weights=0, excluded_nonzero=0, qualified_zero=0, reduced_planes=0, kraw,kqualified;
 reg [1023:0] file_name,out_name,wave;
 function [31:0] step(input [31:0] v);
  reg [31:0] t;begin t=v^(v<<13);t=t^(t>>17);step=t^(t<<5);end
 endfunction
 initial begin
  rc=$value$plusargs("input=%s",file_name);rc=$value$plusargs("output=%s",out_name);
  rc=$value$plusargs("seed=%d",seed);rc=$value$plusargs("traffic=%d",traffic);rc=$value$plusargs("resets=%d",resets);
  rng=seed;
  if($value$plusargs("wave=%s",wave)) begin $dumpfile(wave);$dumpvars(0,check);end
  f=$fopen(file_name,"r");if(!f)$fatal(1,"input unavailable");
  while(!$feof(f)) begin
   rc=$fscanf(f,"%h %h %d\n",xv[count],wv[count],expected[count]);
   if(rc==3)count=count+1;else if(!$feof(f))$fatal(1,"malformed stimulus");
  end
  $fclose(f);o=$fopen(out_name,"w");$fdisplay(o,"ordinal,accept_cycle,emit_cycle,actual_sum,latency");
 end
 always @(negedge clk) begin
  rst=(cycle<2)||(resets&&(cycle==19||cycle==47||cycle==113));
  rng=step(rng);
  orr=(traffic==0)||(traffic==1&&cycle%8==0)||(traffic==2&&rng%5!=0);
  if(resets&&cycle>=10&&cycle<=25)orr=0;
  if(rst)iv=0;
  else if(index<count) begin
   x=xv[index];w=wv[index];
   if(!iv)iv=(traffic!=2)||(rng%4!=0);
  end else iv=0;
 end
 always @(posedge clk) begin
  #0; // Sample after the DUT captures inputs, before nonblocking updates.
  if(rst) begin
   if(tail>head&&!ov)busyreset=busyreset+1;
   if(ov)outputreset=outputreset+1;
   canceled=canceled+tail-head;head=tail;held=0;
  end else begin
   if(held&&(!ov||sum!==held_sum||tag!==held_tag))$fatal(1,"stalled output changed at %0d",cycle);
   held=ov&&!orr;held_sum=sum;held_tag=tag;
   if(ov&&orr) begin
    if(head==tail)$fatal(1,"unsolicited result");
    j=queued[head];
    if(sum!==expected[j]||tag!==(j%256))$fatal(1,"score mismatch ordinal %0d got %0d expected %0d tag %0d",j,sum,expected[j],tag);
    latency=cycle-accepted_cycle[head];total_latency=total_latency+latency;
    if(latency>max_latency)max_latency=latency;
    if(firstemit<0)firstemit=cycle;lastemit=cycle;
    $fdisplay(o,"%0d,%0d,%0d,%0d,%0d",j,accepted_cycle[head],cycle,sum,latency);
    head=head+1;emitted=emitted+1;
   end
   if(iv&&ir) begin
    oracle=0;ub=0;qb=0;neg=0;
    for(j=0;j<N;j=j+1) begin
     a=$signed(x[j*W+:W]);b=$signed(w[j*W+:W]);oracle=oracle+a*b;
     ub=ub|x[j*W+:W];if(a<0)neg=1;
     if(b!=0)qb=qb|x[j*W+:W];
     else begin zero_weights=zero_weights+1;if(a!=0)excluded_nonzero=excluded_nonzero+1;end
    end
    if(oracle!=expected[index])$fatal(1,"independent stimulus oracle mismatch");
    if(qb==0)qualified_zero=qualified_zero+1;
    kraw=0;kqualified=0;for(j=0;j<W;j=j+1)begin kraw=kraw+ub[j];kqualified=kqualified+qb[j];end
    if(kqualified<kraw)reduced_planes=reduced_planes+1;
    if(ub==0)zero_groups=zero_groups+1;if(neg)negative_groups=negative_groups+1;
    queued[tail]=index;accepted_cycle[tail]=cycle;tail=tail+1;
    if(firstaccept<0)firstaccept=cycle;lastaccept=cycle;
    index=index+1;iv=0;
    if(ov&&orr)simultaneous=simultaneous+1;
   end else if(iv&&!ir)installs=installs+1;
   if(ov&&!orr)outstalls=outstalls+1;
  end
  cycle=cycle+1;
  if(index==count&&head==tail&&!ov) begin
   $fclose(o);
   $display("PASS count=%0d emitted=%0d canceled=%0d cycles=%0d firstaccept=%0d lastaccept=%0d firstemit=%0d lastemit=%0d total_latency=%0d max_latency=%0d installs=%0d outstalls=%0d busyreset=%0d outputreset=%0d zero_groups=%0d negative_groups=%0d simultaneous=%0d zero_weights=%0d excluded_nonzero=%0d qualified_zero=%0d reduced_planes=%0d",count,emitted,canceled,cycle,firstaccept,lastaccept,firstemit,lastemit,total_latency,max_latency,installs,outstalls,busyreset,outputreset,zero_groups,negative_groups,simultaneous,zero_weights,excluded_nonzero,qualified_zero,reduced_planes);
   $finish;
  end
  if(cycle>2000000)$fatal(1,"timeout");
  if(cycle==250&&wave!=0)$dumpoff;
 end
endmodule
