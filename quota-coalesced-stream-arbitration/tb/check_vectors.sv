`default_nettype none
module tb;
    localparam N=`N, WIDTH=`WIDTH, Q=`QUOTA, FIXED=`FIXED;
    localparam IW=(N<=1 ? 1 : $clog2(N));
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1, m_ready=0;
    reg [N-1:0] s_valid=0;
    reg [N*WIDTH-1:0] s_data=0;
    wire [N-1:0] s_ready;
    wire m_valid;
    wire [WIDTH-1:0] m_data;
    wire [IW-1:0] m_source;
`ifdef POST_SYNTH
    stream_arbiter dut(.*);
`else
    stream_arbiter #(.N(N),.WIDTH(WIDTH),.QUOTA(Q),.FIXED(FIXED)) dut(.*);
`endif
    integer fd, status, row=0, fires=0, stalls=0, i, warmup=512;
    integer eval_fires=0, switches=0, last_source=-1, max_wait=0;
    integer waits [0:N-1];
    integer services [0:N-1];
    integer vr, mr, ev, es;
    reg [N-1:0] req, er;
    reg [N*WIDTH-1:0] data_in;
    reg [WIDTH-1:0] ed;
    reg previous_stall=0, previous_reset=1;
    reg [WIDTH-1:0] previous_data;
    reg [IW-1:0] previous_source;
    reg [N-1:0] previous_valid, previous_ready;
    reg [N*WIDTH-1:0] previous_input;
    reg [2047:0] filename;
    initial begin
        status=$value$plusargs("WARMUP=%d",warmup);
        for (i=0;i<N;i=i+1) begin waits[i]=0;services[i]=0;end
        if (!$value$plusargs("VECTORS=%s",filename)) $fatal(1,"missing vectors");
        fd=$fopen(filename,"r");
        if (!fd) $fatal(1,"cannot read vectors");
        if ($test$plusargs("WAVE")) begin $dumpfile("wave.vcd"); $dumpvars(0,tb); end
        while (!$feof(fd)) begin
            status=$fscanf(fd,"%d %d %h %h %d %d %h %h\n",vr,mr,req,data_in,ev,es,er,ed);
            if (status!=8) $fatal(1,"invalid vector row %0d",row);
            @(negedge clk);
            rst=vr; m_ready=mr; s_valid=req; s_data=data_in;
            @(posedge clk);
            // Sample before sequential state updates, exactly at the handshake edge.
            if (m_valid!==ev[0] || s_ready!==er ||
                (ev && (m_data!==ed || m_source!==es[IW-1:0])))
                $fatal(1,"scoreboard mismatch row=%0d got=%b,%0d,%h,%h expected=%0d,%0d,%h,%h",
                    row,m_valid,m_source,s_ready,m_data,ev,es,er,ed);
            if ((s_ready & (s_ready-1'b1))!=0 || (s_ready & ~s_valid)!=0)
                $fatal(1,"grant conservation failed");
            if (!rst && previous_stall && !previous_reset) begin
                if (!m_valid || m_data!==previous_data || m_source!==previous_source)
                    $fatal(1,"output changed under backpressure");
            end
            for (i=0;i<N;i=i+1) begin
                if (!rst && !previous_reset && previous_valid[i] && !previous_ready[i])
                    if (!s_valid[i] || s_data[i*WIDTH +: WIDTH]!==previous_input[i*WIDTH +: WIDTH])
                        $fatal(1,"illegal source stimulus on port %0d row %0d",i,row);
            end
            if (m_valid && m_ready) fires=fires+1;
            if (m_valid && !m_ready) stalls=stalls+1;
            if (rst) last_source=-1;
            for (i=0;i<N;i=i+1) begin
                if (rst || !s_valid[i]) waits[i]=0;
                else if (m_valid && m_ready) begin
                    if (m_source==i) begin
                        if (row>=warmup) begin
                            services[i]=services[i]+1;
                            if (waits[i]>max_wait) max_wait=waits[i];
                        end
                        waits[i]=0;
                    end else waits[i]=waits[i]+1;
                end
            end
            if (row>=warmup && m_valid && m_ready) begin
                eval_fires=eval_fires+1;
                if (last_source>=0 && last_source!=m_source) switches=switches+1;
                last_source=m_source;
            end
            previous_stall=m_valid && !m_ready; previous_data=m_data; previous_source=m_source;
            previous_reset=rst; previous_valid=s_valid; previous_ready=s_ready; previous_input=s_data;
            row=row+1;
        end
        $fclose(fd);
        $display("PASS cycles=%0d fires=%0d stalls=%0d eval_fires=%0d switches=%0d wait_max=%0d",row,fires,stalls,eval_fires,switches,max_wait);
        $write("SERVICE");
        for (i=0;i<N;i=i+1) $write(" %0d",services[i]);
        $write("\n");
        $finish;
    end
endmodule
`default_nettype wire
