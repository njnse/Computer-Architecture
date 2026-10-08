module formal_top #(parameter WIDTH=2,MODE=3,OW=2*WIDTH+2)(
    input wire clk,rst,s_valid,m_ready,
    input wire [4*WIDTH-1:0] s_x,s_w,
    input wire [3:0] s_meta
);
    wire s_ready,m_valid,m_error;
    wire signed [OW-1:0] m_data;
    sparse_dot #(.WIDTH(WIDTH),.MODE(MODE)) dut(.*);
    reg [4*WIDTH-1:0] expanded;
    reg [3:0] mask;
    reg bad,seen;
    integer j;
    always @* begin
        mask=0;bad=0;seen=0;expanded=0;
        if(MODE==0)expanded=s_w;
        else begin
            if(MODE==1)begin
                bad=(s_meta[1:0]>=s_meta[3:2]);
                mask=(4'b0001<<s_meta[1:0]) | (4'b0001<<s_meta[3:2]);
            end else if(MODE==2)begin
                case(s_meta[2:0])
                    0:mask=4'b0011;
                    1:mask=4'b0101;
                    2:mask=4'b1001;
                    3:mask=4'b0110;
                    4:mask=4'b1010;
                    5:mask=4'b1100;
                    default:begin mask=0;bad=1;end
                endcase
            end else if(MODE==3)mask=(4'b0001<<s_meta[0]) | (4'b0100<<s_meta[1]);
            else mask=4'b0101;
            for(j=0;j<4;j=j+1)begin
                if(mask[j] && !bad)begin
                    expanded[j*WIDTH +: WIDTH]=seen ? s_w[WIDTH +: WIDTH] : s_w[0 +: WIDTH];
                    seen=1;
                end
            end
        end
    end
    wire signed [2*WIDTH-1:0] product[0:3];
    wire signed [OW-1:0] extended[0:3];
    genvar k;
    generate for(k=0;k<4;k=k+1)begin: reference_products
        assign product[k]=$signed(s_x[k*WIDTH +: WIDTH])*$signed(expanded[k*WIDTH +: WIDTH]);
        assign extended[k]={{2{product[k][2*WIDTH-1]}},product[k]};
    end endgenerate
    wire signed [OW-1:0] reference_sum=extended[0]+extended[1]+extended[2]+extended[3];
    reg started=0,expected_valid=0;
    reg signed [OW-1:0] expected_data;
    reg expected_error;
    always @(posedge clk)begin
        if(!started)assume(rst);
        started<=1;
        if(started)begin
            assert(m_valid==(!rst && expected_valid));
            assert(s_ready==(!rst && (!expected_valid || m_ready)));
            if(m_valid)begin assert(m_data==expected_data);assert(m_error==expected_error);end
            if(!rst && !$past(rst) && $past(m_valid && !m_ready))begin
                assert(m_valid);assert(m_data==$past(m_data));assert(m_error==$past(m_error));
            end
        end
        if(rst)expected_valid<=0;
        else begin
            if(expected_valid && m_ready)expected_valid<=0;
            if(s_valid && s_ready)begin expected_valid<=1;expected_data<=reference_sum;expected_error<=bad;end
        end
    end
endmodule
