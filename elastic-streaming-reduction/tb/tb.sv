`timescale 1ns/1ps
module tb;
    parameter WIDTH=`WIDTH;
    parameter PIPE=`PIPE;
    localparam COUNT=512;
    reg clk=0;
    always #5 clk=~clk;
    reg rst=1,s_valid=0,m_ready=0;
    wire s_ready,m_valid;
    reg [WIDTH-1:0] a=0,b=0,c=0,d=0;
    wire [WIDTH+1:0] m_data;
    reg [4*WIDTH-1:0] vectors[0:COUNT-1];
    reg [WIDTH+1:0] answers[0:COUNT-1];
    reg [WIDTH+1:0] queue[0:COUNT-1];
    integer birth[0:COUNT-1];
    integer head=0,tail=0,source=0;
    integer cycle=0,retired=0,dropped=0,accepted=0,source_stalls=0,sink_stalls=0;
    integer simultaneous=0,max_occupancy=0,reset_pending=0;
    integer lat_min=100000,lat_max=0,lat_sum=0,latency=0;
    integer first_output=-1,last_output=-1,max_output_gap=0;
    integer scenario,seed,ignored;
    reg [31:0] rng;
    reg previous_stall=0;
    reg source_held=0;
    reg [4*WIDTH-1:0] previous_source;
    reg [WIDTH+1:0] previous_data;
    string vector_file,answer_file;
    function [31:0] advance(input [31:0] x);
        begin advance=(x<<1) ^ ((x[31]) ? 32'h04c11db7 : 0); end
    endfunction
`ifdef POST_SYNTH
    stream_sum dut(.clk(clk),.rst(rst),.s_valid(s_valid),.s_ready(s_ready),
        .a(a),.b(b),.c(c),.d(d),.m_valid(m_valid),.m_ready(m_ready),.m_data(m_data));
`else
    stream_sum #(.WIDTH(WIDTH),.PIPE(PIPE)) dut(.clk(clk),.rst(rst),.s_valid(s_valid),.s_ready(s_ready),
        .a(a),.b(b),.c(c),.d(d),.m_valid(m_valid),.m_ready(m_ready),.m_data(m_data));
`endif
    initial begin
        ignored=$value$plusargs("VECTORS=%s",vector_file);
        ignored=$value$plusargs("ANSWERS=%s",answer_file);
        ignored=$value$plusargs("SEED=%d",seed);
        ignored=$value$plusargs("SCENARIO=%d",scenario);
        rng=seed+1;
        $readmemh(vector_file,vectors);
        $readmemh(answer_file,answers);
        if ($test$plusargs("WAVE")) begin $dumpfile("wave.vcd"); $dumpvars(0,tb); end
        for (cycle=0;cycle<20000;cycle=cycle+1) begin
            @(negedge clk);
            rst=(cycle<2) || (scenario==2 && (cycle==20 || cycle==21 || cycle==120 || cycle==121));
            rng=advance(rng);
            m_ready=(scenario==0) ? 1 : rng[5:4]!=0;
            if (scenario==2 && ((cycle>=15 && cycle<=30)||(cycle>=110 && cycle<=130))) m_ready=0;
            if (rst) s_valid=0;
            else if (!source_held) begin
                s_valid=(source<COUNT) && ((scenario==0) || rng[2:1]!=0);
            end
            if (source<COUNT) {a,b,c,d}=vectors[source];
            @(posedge clk);
            if (rst) begin
                if (tail>head) reset_pending=reset_pending+1;
                dropped=dropped+(tail-head);head=0;tail=0;previous_stall=0;source_held=0;
            end else begin
                if (previous_stall && (!m_valid || m_data!==previous_data)) $fatal(1,"unstable stalled output");
                if (source_held && (!s_valid || {a,b,c,d}!==previous_source)) $fatal(1,"unstable stalled source");
                source_held=s_valid && !s_ready;previous_source={a,b,c,d};
                previous_stall=m_valid && !m_ready;previous_data=m_data;
                if (s_valid && !s_ready) source_stalls=source_stalls+1;
                if (m_valid && !m_ready) sink_stalls=sink_stalls+1;
                if (s_valid && s_ready && m_valid && m_ready) simultaneous=simultaneous+1;
                if (m_valid && m_ready) begin
                    if (head>=tail) $fatal(1,"output without accepted input");
                    if (m_data!==queue[head]) $fatal(1,"scoreboard mismatch got %h expected %h",m_data,queue[head]);
                    latency=cycle-birth[head];
                    if(latency<lat_min)lat_min=latency;
                    if(latency>lat_max)lat_max=latency;
                    lat_sum=lat_sum+latency;head=head+1;retired=retired+1;
                    if(first_output<0)first_output=cycle;
                    if(last_output>=0 && cycle-last_output>max_output_gap)max_output_gap=cycle-last_output;
                    last_output=cycle;
                end
                if (s_valid && s_ready) begin
                    queue[tail]=answers[source];birth[tail]=cycle;
                    tail=tail+1;source=source+1;accepted=accepted+1;
                end
                if(tail-head>max_occupancy)max_occupancy=tail-head;
                if(tail-head>PIPE) $fatal(1,"capacity exceeded");
                if (source==COUNT && tail==head) begin
                    if(retired+dropped!=accepted)$fatal(1,"conservation failure");
                    if(scenario==0 && (lat_min!=PIPE || lat_max!=PIPE))$fatal(1,"unexpected clean latency");
                    if(scenario!=0 && (source_stalls==0 || sink_stalls==0))$fatal(1,"stall coverage missing");
                    if(scenario==2 && reset_pending==0)$fatal(1,"pending-reset coverage missing");
                    if(scenario==0 && max_output_gap!=1)$fatal(1,"unexpected clean initiation interval");
                    $display("RESULT %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                        WIDTH,PIPE,seed,scenario,accepted,retired,dropped,cycle-1,
                        lat_min,lat_max,lat_sum,source_stalls,sink_stalls,simultaneous,reset_pending,
                        first_output,last_output,max_output_gap);
                    $finish;
                end
            end
        end
        $fatal(1,"timeout");
    end
endmodule
