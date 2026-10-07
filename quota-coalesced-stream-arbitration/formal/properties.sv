module formal_top #(
    parameter N=3, WIDTH=2, QUOTA=4, FIXED=0,
    parameter IW=(N<=1 ? 1 : $clog2(N))
) (
    input wire clk,rst,m_ready,
    input wire [N-1:0] s_valid,
    input wire [N*WIDTH-1:0] s_data
);
    wire [N-1:0] s_ready;
    wire m_valid;
    wire [WIDTH-1:0] m_data;
    wire [IW-1:0] m_source;
    stream_arbiter #(.N(N),.WIDTH(WIDTH),.QUOTA(QUOTA),.FIXED(FIXED)) dut(.*);
    reg started=0;
    reg [7:0] wait_count [0:N-1];
    integer i;
    always @(posedge clk) begin
        started<=1;
        for (i=0;i<N;i=i+1) begin
            if (rst || !s_valid[i] || s_ready[i]) wait_count[i]<=0;
            else if (m_valid && m_ready) wait_count[i]<=wait_count[i]+1;
            if (started && !rst) begin
                if (!$past(rst) && $past(s_valid[i] && !s_ready[i])) begin
                    assume(s_valid[i]);
                    assume(s_data[i*WIDTH +: WIDTH]==$past(s_data[i*WIDTH +: WIDTH]));
                end
                if (!FIXED) assert(wait_count[i]<=(N-1)*QUOTA);
                if (s_ready[i]) assert(m_data==s_data[i*WIDTH +: WIDTH] && m_source==i);
            end
        end
        if (started) begin
            if (rst) begin assert(!m_valid); assert(s_ready==0); end
            else begin
                assert(m_valid==(|s_valid));
                assert((s_ready & (s_ready-1'b1))==0);
                assert((s_ready & ~s_valid)==0);
                assert((|s_ready)==(m_valid && m_ready));
                if (!$past(rst) && $past(m_valid && !m_ready)) begin
                    assert(m_valid);
                    assert(m_data==$past(m_data));
                    assert(m_source==$past(m_source));
                end
            end
        end
    end
endmodule
