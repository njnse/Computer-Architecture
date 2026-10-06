module stream_sum #(
    parameter integer WIDTH = 16,
    parameter integer PIPE = 1
) (
    input wire clk, input wire rst,
    input wire s_valid, output wire s_ready,
    input wire [WIDTH-1:0] a,b,c,d,
    output wire m_valid, input wire m_ready,
    output wire [WIDTH+1:0] m_data
);
    generate
    if (PIPE == 1) begin: single
        reg valid;
        reg [WIDTH+1:0] value;
        wire enable = !valid || m_ready;
        wire [WIDTH:0] ab = {1'b0,a} + {1'b0,b};
        wire [WIDTH:0] cd = {1'b0,c} + {1'b0,d};
        assign s_ready = !rst && enable;
        assign m_valid = !rst && valid;
        assign m_data = value;
        always @(posedge clk) begin
            if (rst) valid <= 1'b0;
            else if (enable) begin
                valid <= s_valid;
                if (s_valid) value <= {1'b0,ab} + {1'b0,cd};
            end
        end
    end else begin: split
        reg v0,v1;
        reg [WIDTH:0] ab,cd;
        reg [WIDTH+1:0] value;
        wire r1 = !v1 || m_ready;
        wire r0 = !v0 || r1;
        assign s_ready = !rst && r0;
        assign m_valid = !rst && v1;
        assign m_data = value;
        always @(posedge clk) begin
            if (rst) begin v0 <= 1'b0; v1 <= 1'b0; end
            else begin
                if (r0) begin
                    v0 <= s_valid;
                    if (s_valid) begin
                        ab <= {1'b0,a} + {1'b0,b};
                        cd <= {1'b0,c} + {1'b0,d};
                    end
                end
                if (r1) begin
                    v1 <= v0;
                    if (v0) value <= {1'b0,ab} + {1'b0,cd};
                end
            end
        end
    end
    endgenerate
endmodule
