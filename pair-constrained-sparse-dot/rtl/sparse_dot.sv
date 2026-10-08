module sparse_dot #(
    parameter WIDTH=4, MODE=3, CHECK_META=1,
    parameter OW=2*WIDTH+2
) (
    input wire clk, rst, s_valid, m_ready,
    input wire [4*WIDTH-1:0] s_x, s_w,
    input wire [3:0] s_meta,
    output wire s_ready, m_valid,
    output wire signed [OW-1:0] m_data,
    output wire m_error
);
    wire signed [WIDTH-1:0] x [0:3];
    wire signed [WIDTH-1:0] w [0:3];
    genvar k;
    generate for (k=0;k<4;k=k+1) begin: unpack
        assign x[k]=s_x[k*WIDTH +: WIDTH];
        assign w[k]=s_w[k*WIDTH +: WIDTH];
    end endgenerate
    wire signed [OW-1:0] result;
    wire error;
    generate if (MODE==0) begin: dense
        wire signed [2*WIDTH-1:0] p0=x[0]*w[0], p1=x[1]*w[1];
        wire signed [2*WIDTH-1:0] p2=x[2]*w[2], p3=x[3]*w[3];
        wire signed [OW-1:0] e0={{2{p0[2*WIDTH-1]}},p0};
        wire signed [OW-1:0] e1={{2{p1[2*WIDTH-1]}},p1};
        wire signed [OW-1:0] e2={{2{p2[2*WIDTH-1]}},p2};
        wire signed [OW-1:0] e3={{2{p3[2*WIDTH-1]}},p3};
        assign result=(e0+e1)+(e2+e3);
        assign error=1'b0;
    end else begin: sparse
        wire [1:0] i0,i1;
        if (MODE==1) begin: indices
            assign i0=s_meta[1:0];
            assign i1=s_meta[3:2];
            assign error=CHECK_META && (i0>=i1);
        end else if (MODE==2) begin: compact
            reg [3:0] decoded;
            always @* begin
                case (s_meta[2:0])
                    0: decoded={2'd1,2'd0};
                    1: decoded={2'd2,2'd0};
                    2: decoded={2'd3,2'd0};
                    3: decoded={2'd2,2'd1};
                    4: decoded={2'd3,2'd1};
                    5: decoded={2'd3,2'd2};
                    default: decoded=0;
                endcase
            end
            assign i0=decoded[1:0];
            assign i1=decoded[3:2];
            assign error=CHECK_META && (s_meta[2:0]>=6);
        end else if (MODE==3) begin: paired
            assign i0={1'b0,s_meta[0]};
            assign i1={1'b1,s_meta[1]};
            assign error=1'b0;
        end else begin: fixed_pair
            assign i0=0;
            assign i1=2;
            assign error=1'b0;
        end
        wire signed [WIDTH-1:0] a0=x[i0],a1=x[i1];
        wire signed [2*WIDTH-1:0] p0=a0*w[0],p1=a1*w[1];
        wire signed [OW-1:0] e0={{2{p0[2*WIDTH-1]}},p0};
        wire signed [OW-1:0] e1={{2{p1[2*WIDTH-1]}},p1};
        assign result=error ? {OW{1'b0}} : e0+e1;
    end endgenerate
    reg occupied;
    reg signed [OW-1:0] data;
    reg fault;
    assign s_ready=!rst && (!occupied || m_ready);
    assign m_valid=!rst && occupied;
    assign m_data=data;
    assign m_error=fault;
    always @(posedge clk) begin
        if (rst) begin
            occupied<=0;
            data<=0;
            fault<=0;
        end else if (s_ready) begin
            occupied<=s_valid;
            if (s_valid) begin
                data<=result;
                fault<=error;
            end
        end
    end
endmodule
