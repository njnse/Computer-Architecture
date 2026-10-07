`default_nettype none
// Independent ready/valid beats; this is not a packet or AXI arbiter.
module stream_arbiter #(
    parameter integer N=4,
    parameter integer WIDTH=16,
    parameter integer QUOTA=4,
    parameter integer FIXED=0,
    parameter integer IW=(N<=1 ? 1 : $clog2(N))
) (
    input wire clk, rst,
    input wire [N-1:0] s_valid,
    input wire [N*WIDTH-1:0] s_data,
    output reg [N-1:0] s_ready,
    output reg m_valid,
    output reg [WIDTH-1:0] m_data,
    output reg [IW-1:0] m_source,
    input wire m_ready
);
    localparam CW=(QUOTA<=1 ? 1 : $clog2(QUOTA));
    reg [IW-1:0] pointer, owner, lock_owner;
    reg [CW-1:0] remaining;
    reg locked;
    reg [IW-1:0] first_any, first_masked, selected;
    reg found_any, found_masked;
    integer i;
    // Two parallel priority searches implement cyclic masked selection.
    always @* begin
        first_any=0; first_masked=0; found_any=0; found_masked=0;
        for (i=0; i<N; i=i+1) begin
            if (s_valid[i] && !found_any) begin
                first_any=i; found_any=1;
            end
            if (s_valid[i] && i>=pointer && !found_masked) begin
                first_masked=i; found_masked=1;
            end
        end
        selected=FIXED ? first_any : (found_masked ? first_masked : first_any);
        if (!FIXED && QUOTA>1 && remaining!=0 && s_valid[owner]) selected=owner;
        if (locked) selected=lock_owner;
        m_valid=0; m_data=0; m_source=0; s_ready=0;
        if (!rst && found_any) begin
            m_valid=1;
            m_source=selected;
            m_data=s_data[selected*WIDTH +: WIDTH];
            s_ready[selected]=m_ready;
        end
    end
    always @(posedge clk) begin
        if (rst) begin
            pointer<=0; owner<=0; remaining<=0; locked<=0; lock_owner<=0;
        end else begin
            // Capture selection while blocked, including late arrivals.
            locked<=m_valid && !m_ready;
            if (m_valid && !m_ready) lock_owner<=selected;
            // An idle interval expires a partial quota but preserves scan history.
            if (!found_any) remaining<=0;
            if (m_valid && m_ready) begin
                pointer <= (selected==N-1) ? 0 : selected+1'b1;
                owner <= selected;
                if (remaining!=0 && owner==selected) remaining<=remaining-1'b1;
                else remaining<=QUOTA-1;
            end
        end
    end
endmodule
`default_nettype wire
