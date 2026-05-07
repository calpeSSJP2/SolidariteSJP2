##Super1:  username:calpe2, abel1 :This properly works on both admin page and  custome webpage
##Go in as admin  http://127.0.0.1:8000/admin/
#register =http://127.0.0.1:8000/accounts/register/
##
##>> rm db.sqlite3   ##clean everythin in database, make migration . 1.register, 2.sec gives account ssjps, 3.then memeber account
##It manager Calpe, Calpe@2026
## IT Technicien: KarpoT, calpeT@2026  SQL=Popos@2026 ((venv) PS C:\--\SolidariteSJP2> mysql -u root -p
#It manager Kalpe, calpe@2026
##SECRETARY    Armanda |  arma@2026
#Manager   gygy    psw:lydw@2025 okRun
#Officer2  Eugeni     magni@2025  okrun
#customer:  kayit , pacis@2025  okRun1
#cusromer: Evodus@1 ,PapaBerth@2025
#Auditor   PTrinity       Alfo@2026 ok  by using reset template
##Licardo  gladis@2025
##Verifier   diane@2026 or 5    mentus@2025 notYet
##Fabus yvonne@2026

##SECREATRY    Muhorak //lydwn@2026
##ISUE User → MembersProfile → MemberAccount,FTER LOGIN I CANT http://127.0.0.1:8000/transactions1/deposit/
##THIS CAN NOT WORK self.request.user.account .
##IN MODEL ABSTRACTUSER ADD In your User model (which subclasses AbstractUser), add this:
#@property
#def account(self):
 #   try:
 #       return self.membersprofile.memberaccount
 #   except MemberAccount.DoesNotExist:
 #       return None

##Lesson1 Use of Loan.objects.filter(account=self.request.user.account) [who is online], and Loan.objects.all() [for all users]
 ##1. class User(AbstractUser):
##2. class MembersProfile(models.Model): ##Fname,Lname are in user model
   #user = models.OneToOneField(User, on_delete=models.CASCADE)
##3. class MemberAccount(models.Model):  ##Thes models are for account creation .About other transaction go in tranction models and import thes account
  #member = models.ForeignKey(MembersProfile, on_delete=models.CASCADE) ##MemberAccount has a ForeignKey to MembersProfile, meaning one member can have multiple accounts..
   ## member = models.OneToOneField(MembersProfile, on_delete=models.CASCADE)
##4.class Loan(models.Model):
##account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE, related_name='loans') ##Not in the same folder
##Observation, account in loan depends to class memeberAccount,
# the member in memberAccount,is linked to memberProfile, user in  memberprofile is linked to class User(abstract)
##To get usermodel, the system provide th sequence link. account.loan observes uperclass with foreignerkeys.
# account.loan (4)->#member.MemberAccount (3) -->user.MembersProfile(2)-->User (root)
##it is why Loan.objects.filter(account=self.request.user.account), ##self.request.user ni user  who is login 0787474684  heshima

##1. ibizongerwamo: receite nbr/refrence, uploat,, check recipt if is not entered
##2. ingoboka interest 1%
##3. allocate acount createe to secreatary
##4. Add shares on form as you filter ,see them
##5. to initialize each membership at 5000 dor ikimina
##6. create a model to manage operation ssjp2 acount (purchase items , name ,cost, (debit ssjp2)
##7. loan officer guhabwa for for loan request
##8. share prinicpal: coefficient = personal principal/totol principal
##9. personal share = coefficient*total share
##10. interest = [penalities+interst at goshen-bank charges , ssjpe expenditutes]]
##Test, During payment the system accept the negative .As long as you pay we need to notifiy and return the rest on my account of customers,,
##Also add profit to solidarity StJp2

# Test, As long as you get loan, we need to minimze balance, checkk
##ACCESS TO SSJP2 Account
##Validate on loan form, if balance loan >=0, dont accept to add a new, unless top up
##Don't give loan anyone who has it ,but topup
##check PYTM underpayment, late while paying amount loan, we also need the due date, and pymtn date //Call the froms compare the one we have using view,..
##Checks loans, their PYMT IF THEY AFFECT BALANCE PERSONNEL
##Add filter bar, excell pfd ,...
##ADD Visual dialog box, to display errors on front end
##Lend oK tuzajya dulora payment ijya kureba niba lender adafite uwamwisjingiye
##Create account representing Equit_,,and microfinance
##INSTALLED APPS
##1.pip install django-widget-tweaks
##del db.sqlite3
#Remove-Item accounts\migrations\*.py -Exclude __init__.py
#Remove-Item transact1_regular_deposit\migrations\*.py -Exclude __init__.py, remove everything exept __init__
##python manage.py flush Resets everything (users, accounts, transactions, ledger).
##Problems: Balance is doubled in both ssj2_account and customers. Balance at account, is not updated'
##Withraw, transfer also also removes double
##from accounts.models import MemberAccount
##MemberAccount.objects.all()
##<QuerySet [<MemberAccount: Monique KAYITESI - SSJP2-001-2026>, <MemberAccount: Calpe Nkika - SSJP2-002-2026>, <MemberAccount: Gystav1 NTAKIYE1 - SSJP2-003-2026>,
 ##<MemberAccount: Alphonse Papatrinity - SSJP2-004-2026>, <MemberAccount: Eugenia MamaMagnie - SSJP2-005-2026>]>
##>>> due_date = date(2025, 12, 5) # 5 December 2025 >>> paid_on = date(2026, 5, 2) # 2 May 2026 >>> amount = Decimal('40000')