`ifndef WIDTH
`define WIDTH 4
`endif
`ifndef MODE
`define MODE 3
`endif
module tb;
    localparam WIDTH=`WIDTH,MODE=`MODE,OW=2*WIDTH+2;
    reg clk=0;
    reg rst,s_valid,m_ready;
    reg [4*WIDTH-1:0] s_x,s_w;
    reg [3:0] s_meta;
    wire s_ready,m_valid,m_error;
    wire signed [OW-1:0] m_data;
`ifdef NETLIST
    sparse_dot dut(.*);
`else
    sparse_dot #(.WIDTH(WIDTH),.MODE(MODE)) dut(.*);
`endif
    integer f,status,er,ev,ed,ee,cycle=0,accepted=0,emitted=0,canceled=0,stalls=0,errors=0;
    integer simultaneous=0,negative=0,min_seen=0,max_seen=0,reset_busy=0;
    integer meta_hist[0:15];
    integer latency_hist[0:255];
    integer accepted_at=-1,latency;
    integer i;
    reg busy=0,was_stalled=0;
    reg signed [OW-1:0] old_data;
    reg old_error;
    string vectors,outputs,wave;
    integer of;
    initial begin
        for(i=0;i<16;i=i+1)meta_hist[i]=0;
        for(i=0;i<256;i=i+1)latency_hist[i]=0;
        if(!$value$plusargs("vectors=%s",vectors))$fatal(1,"Missing vectors");
        f=$fopen(vectors,"r");if(!f)$fatal(1,"Cannot open vectors");
        of=0;
        if($value$plusargs("outputs=%s",outputs))of=$fopen(outputs,"w");
        if($value$plusargs("wave=%s",wave))begin $dumpfile(wave);$dumpvars(0,tb);end
        while(!$feof(f))begin
            status=$fscanf(f,"%d %d %d %h %h %h %d %d %d %d\n",rst,s_valid,m_ready,s_x,s_w,s_meta,er,ev,ed,ee);
            if(status!=10)$fatal(1,"Malformed vector cycle %0d",cycle);
            #5;
            if(s_ready!==er[0] || m_valid!==ev[0])$fatal(1,"Handshake mismatch cycle %0d",cycle);
            if(m_valid && (m_data!==ed[OW-1:0] || m_error!==ee[0]))$fatal(1,"Arithmetic mismatch cycle %0d got %0d expected %0d",cycle,m_data,ed);
            if(was_stalled && !rst && (!m_valid || m_data!==old_data || m_error!==old_error))$fatal(1,"Output changed while stalled");
            was_stalled=m_valid && !m_ready;
            old_data=m_data;old_error=m_error;
            if(rst)begin
                if(busy)begin canceled=canceled+1;reset_busy=reset_busy+1;end
                busy=0;accepted_at=-1;
            end else begin
                if(m_valid && m_ready)begin
                    emitted=emitted+1;errors=errors+m_error;
                    if(m_data<0)negative=negative+1;
                    if(of)$fdisplay(of,"%0d %0d",m_data,m_error);
                    if(!busy)$fatal(1,"Phantom output");
                    latency=cycle-accepted_at;
                    if(latency>255)$fatal(1,"Latency coverage overflow");
                    latency_hist[latency]=latency_hist[latency]+1;
                    busy=0;
                end
                if(s_valid && s_ready)begin
                    accepted=accepted+1;busy=1;accepted_at=cycle;
                    meta_hist[s_meta]=meta_hist[s_meta]+1;
                    for(i=0;i<4;i=i+1)begin
                        if(s_x[i*WIDTH +: WIDTH]==(1<<(WIDTH-1)))min_seen=min_seen+1;
                        if(s_x[i*WIDTH +: WIDTH]==((1<<(WIDTH-1))-1))max_seen=max_seen+1;
                    end
                end
                if(s_valid && !s_ready)stalls=stalls+1;
                if(s_valid && s_ready && m_valid && m_ready)simultaneous=simultaneous+1;
            end
            clk=1;#5;clk=0;cycle=cycle+1;
        end
        if(busy || accepted!=emitted+canceled)$fatal(1,"Transfer conservation failure");
        $display("PASS cycles=%0d accepted=%0d emitted=%0d canceled=%0d stalls=%0d errors=%0d simultaneous=%0d negative=%0d min=%0d max=%0d reset_busy=%0d",cycle,accepted,emitted,canceled,stalls,errors,simultaneous,negative,min_seen,max_seen,reset_busy);
        for(i=0;i<16;i=i+1)$display("META %0d %0d",i,meta_hist[i]);
        for(i=0;i<256;i=i+1)if(latency_hist[i])$display("LATENCY %0d %0d",i,latency_hist[i]);
        $finish;
    end
endmodule
