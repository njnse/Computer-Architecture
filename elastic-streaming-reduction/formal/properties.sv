module formal_top #(
    parameter integer WIDTH=4,
    parameter integer PIPE=1
) (
    input wire clk,rst,s_valid,m_ready,
    input wire [WIDTH-1:0] a,b,c,d
);
    wire s_ready,m_valid;
    wire [WIDTH+1:0] m_data;
    reg [2:0] balance;
    reg started;
    stream_sum #(.WIDTH(WIDTH),.PIPE(PIPE)) dut(
        .clk(clk),.rst(rst),.s_valid(s_valid),.s_ready(s_ready),
        .a(a),.b(b),.c(c),.d(d),.m_valid(m_valid),.m_ready(m_ready),.m_data(m_data));
    always @(posedge clk) begin
        started <= 1'b1;
        if (rst) balance <= 0;
        else begin
            case ({s_valid && s_ready,m_valid && m_ready})
                2'b10: balance <= balance+1;
                2'b01: balance <= balance-1;
            endcase
        end
        if (started && !rst) begin
            assert(balance <= PIPE);
            if (m_valid) assert(balance>0);
            if (!$past(rst) && $past(m_valid && !m_ready)) begin
                assert(m_valid);
                assert(m_data == $past(m_data));
            end
        end
        if (rst) begin assert(!s_ready);assert(!m_valid);end
    end
endmodule
