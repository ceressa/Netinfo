namespace Netinfo.Services
{
    public interface IAdminAuthService
    {
        bool ValidatePassword(string password);
    }
}
