namespace Netinfo.Models;

public class ErrorViewModel
{
    public string? RequestId { get; set; }

    public bool ShowRequestId => !string.IsNullOrEmpty(RequestId);

    public string CustomErrorMessage => 
        "Oops! It seems the page you're looking for doesn't exist or an unexpected error occurred. Please try again later.";
}
