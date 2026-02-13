module watchdog (
    input  wire clk,
    input  wire reset_n,
    input  wire error_flag,
    output reg  [1:0] state
);

localparam SAFE_STATE  = 2'b00;
localparam RUN_STATE   = 2'b01;
localparam ERROR_STATE = 2'b10;

always @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
        state <= SAFE_STATE;
    end else begin
        case (state)
            SAFE_STATE:  if (!error_flag) state <= RUN_STATE;
            RUN_STATE:   if (error_flag)  state <= ERROR_STATE;
            ERROR_STATE: if (!error_flag) state <= SAFE_STATE;
            default:     state <= SAFE_STATE;
        endcase
    end
end

endmodule
